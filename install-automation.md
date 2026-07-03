Great instinct — this is exactly the kind of thing IaC is for. There's no single "best"; the right tool depends on
  when in a machine's life you want the cert to land. Let me give you the decision rule, then concrete recipes for the
  two that fit your case best.

  The decision rule: it's about lifecycle stage, not tool preference

  Machine lifecycle:   [ build image ]──►[ first boot ]──►[ running, ongoing ]
  Best tool:              Packer            cloud-init        Ansible
                          (bake in)         (inject at         (enforce + fix drift)
                                             creation)

  ┌──────────────────────┬───────────────┬───────────────────────────────────────────┬─────────────────────────────┐
  │       Approach       │ When it runs  │                Best when…                 │          Weakness           │
  ├──────────────────────┼───────────────┼───────────────────────────────────────────┼─────────────────────────────┤
  │ Golden image         │ Once, at      │ You spin up many identical VMs from your  │ Rebuild image to rotate the │
  │ (Packer/Image        │ image build   │ own base image                            │  CA; stale images keep old  │
  │ Builder)             │               │                                           │ trust                       │
  ├──────────────────────┼───────────────┼───────────────────────────────────────────┼─────────────────────────────┤
  │                      │ First boot of │ You provision VMs from stock cloud images │ Only runs at first boot; no │
  │ cloud-init           │  each VM      │  and want it baked in "at creation" —     │  ongoing enforcement        │
  │                      │               │ exactly what you described                │                             │
  ├──────────────────────┼───────────────┼───────────────────────────────────────────┼─────────────────────────────┤
  │                      │ Any time,     │ You want one source of truth, idempotent  │ Needs SSH reachability +    │
  │ Ansible (push)       │ repeatedly    │ re-runs, and drift correction across an   │ inventory                   │
  │                      │               │ existing fleet                            │                             │
  └──────────────────────┴───────────────┴───────────────────────────────────────────┴─────────────────────────────┘

  My recommendation for you: Ansible as the source of truth, optionally seeded by cloud-init at creation. Ansible
  because it's agentless (just SSH), idempotent, trivially handles a mixed Debian/RHEL fleet, and — critically —
  re-running it fixes any machine that drifted or was missed. cloud-init is the perfect complement: it gets the cert on
  the box at first boot so the machine is useful before Ansible ever reaches it. Puppet/Chef/Salt are fine but are
  pull-model agents you'd have to run — overkill unless you already operate them.

  ---
  Recipe 1 — Ansible role (the workhorse)

  The whole job is: drop the PEM in the right per-distro directory, then run the right update command only if the file
  changed. Handlers give you that idempotency for free.

  roles/root_ca/tasks/main.yml:
  - name: Install root CA (Debian/Ubuntu)
    copy:
      src: ca.crt
      dest: /usr/local/share/ca-certificates/cybertron-root.crt  # MUST end in .crt
      owner: root
      mode: '0644'
    when: ansible_os_family == "Debian"
    notify: update-ca-debian

  - name: Install root CA (RHEL/Fedora)
    copy:
      src: ca.crt
      dest: /etc/pki/ca-trust/source/anchors/cybertron-root.crt
      owner: root
      mode: '0644'
    when: ansible_os_family == "RedHat"
    notify: update-ca-redhat

  roles/root_ca/handlers/main.yml:
  - name: update-ca-debian
    command: update-ca-certificates

  - name: update-ca-redhat
    command: update-ca-trust extract

  Put your pki/root/certs/ca.crt at roles/root_ca/files/ca.crt. Then:
  ansible-playbook -i inventory.ini site.yml

  Why this shape:
  - Per-distro paths, because Debian uses /usr/local/share/ca-certificates/*.crt (filename must end in .crt) and RHEL
  uses /etc/pki/ca-trust/source/anchors/.
  - notify handler means the expensive update-ca-* only runs when the cert is new or changed — so re-running the
  playbook over 500 machines is cheap and safe.
  - Idempotent: run it daily via cron/AWX/Tower and every machine self-heals back to the correct trust state. That's
  your drift correction.
  - This same role rotates the CA: change ca.crt, re-run, done.

  ---
  Recipe 2 — cloud-init (inject at VM creation)

  cloud-init has a purpose-built ca_certs module. Drop this in user-data when you create the VM (Terraform user_data,
  --user-data flag, etc.):

  #cloud-config
  ca_certs:
    trusted:
      - |
        -----BEGIN CERTIFICATE-----
        MIIB...your root ca.crt contents...
        -----END CERTIFICATE-----

  cloud-init writes it to the right place and runs the update command for the distro automatically — no per-distro logic
  needed. This is the cleanest "at creation" hook and matches your phrasing exactly.

  ---
  A few things that bite people

  - Distribute the cert, never the key. ca.crt is public — committing it to your IaC repo or baking it into user-data is
  fine. ca.key must never leave the (ideally offline) root. Your two-tier design already supports keeping the root
  offline while this automation only ever touches the public cert.
  - Firefox ignores the OS trust store. It uses its own NSS database. If you have Firefox on these machines, you need an
  extra step (an enterprise policy policies.json with Certificates.Install, or certutil against each profile).
  Chrome/curl/most apps respect the OS store and are covered by the above.
  - Rotation plan matters more than install. Your root is valid 10 years, so this is rare — but when it happens, the
  Ansible role is your friend: it can push the new root alongside the old (both trusted during overlap) and remove the
  old one later. Golden images can't do that without a rebuild, which is the main reason I'd anchor on Ansible.
  - Containers are separate. If services run in Docker/Podman, the container has its own trust store — you bake the CA
  into the image or mount it, independent of the host.

  ---

  Proxmox changes the calculus, because Proxmox is fundamentally a template-and-clone platform with two different guest
  types that need different handling. cloud-init only natively helps one of them.

  The key split: VMs vs LXC behave differently

  Proxmox guest
  ├── KVM VM      → cloud-init works natively (Proxmox has built-in support)
  └── LXC container → cloud-init usually does NOT run; needs pct push/exec or template bake

  If you try to use one mechanism for both, you'll fight the platform. So:

  My recommendation: bake into templates, enforce with Ansible

  Because your workflow is "build a golden template once, clone it many times," the highest-leverage move is to put the
  CA into the base template — then every clone (VM or LXC) is born already trusting it, with zero per-guest config.
  Ansible then becomes your enforcement/rotation layer for anything created before the template was updated or that
  drifted.

  1. Bake CA into base templates  ←  covers all future clones automatically
  2. Ansible enforces + rotates   ←  covers existing guests, drift, CA rotation

  Here's each path concretely.

  ---
  VMs (KVM) — Proxmox native cloud-init

  Proxmox has first-class cloud-init. Put your ca_certs block in a snippet and point the VM's cloud-init at it. One-time
  setup on the Proxmox host:

  1. Enable "snippets" content on a storage (e.g. via GUI: Datacenter → Storage → local → add Snippets), giving you
  /var/lib/vz/snippets/.
  2. Create /var/lib/vz/snippets/ca-user.yml:
  #cloud-config
  ca_certs:
    trusted:
      - |
        -----BEGIN CERTIFICATE-----
        MIIB...your pki/root/certs/ca.crt contents...
        -----END CERTIFICATE-----
  3. Attach it to your VM template:
  qm set <vmid> --cicustom "user=local:snippets/ca-user.yml"

  Every clone of that template boots, cloud-init runs, the CA lands in the trust store and
  update-ca-certificates/update-ca-trust runs automatically — no per-distro logic needed. This matches your "install
  after creating" goal exactly.

  ---
  LXC containers — bake the template, or push from the host

  cloud-init generally won't run in stock Proxmox LXC templates, so use one of these:

  Best — bake a custom LXC template (do once):
  pct create 9000 <base-template> --hostname ca-base ...   # spin up a base container
  pct start 9000
  pct push 9000 /path/to/ca.crt /usr/local/share/ca-certificates/cybertron-root.crt
  pct exec 9000 -- update-ca-certificates
  pct stop 9000
  # convert to a reusable template:
  vzdump 9000 ... # then store as template, or use pct template on a stopped CT
  Every future container cloned from this template is born trusting your root.

  Ad-hoc / existing containers — host-side push (great in a loop):
  for id in $(pct list | awk 'NR>1{print $1}'); do
    pct push $id /path/to/ca.crt /usr/local/share/ca-certificates/cybertron-root.crt
    pct exec $id -- update-ca-certificates
  done
  This runs straight from the Proxmox host — no SSH into the containers needed. (Swap paths to
  /etc/pki/ca-trust/source/anchors/ + update-ca-trust for RHEL-family containers.)

  ---
  Tying it together as IaC

  For a fully declarative setup, two clean combos:

  - Terraform (bpg/proxmox provider — the actively maintained one) to define/clone guests, feeding the cloud-init
  snippet to VMs. Infrastructure described in code, CA baked at creation.
  - Ansible with the community.general.proxmox connection plugin — it manages LXC containers through pct exec via the
  Proxmox API, so you can run the root-CA role I sketched earlier against containers without SSH in them. For VMs, plain
  SSH inventory. One playbook, both guest types, idempotent, fixes drift, and handles the eventual CA rotation by
  pushing the new cert and retiring the old.

  So the layered answer: cloud-init snippet for VMs + a baked LXC template get the CA on every new guest at birth;
  Ansible (via the pct connection for LXC, SSH for VMs) is the source of truth that enforces it everywhere and rotates
  it when the 10-year root eventually changes.

  ---
  A couple of Proxmox-specific gotchas:
  - The CA cert is public — fine to store in a snippet, a template, or your Terraform repo. The root key never touches
  any of this; keep it offline per your existing design.
  - Unprivileged LXC still uses the normal trust-store paths, so pct push + update-ca-certificates works the same as
  privileged.
  - Alpine LXC (common for lightweight containers) uses /usr/local/share/ca-certificates/ + update-ca-certificates from
  the ca-certificates package — install that package first if it's a minimal image.

  Want me to scaffold this into your repo — the #cloud-config snippet, a pct-based bootstrap script for LXC, and the
  Ansible role wired to use the Proxmox pct connection for containers and SSH for VMs? I can lay it all out under an
  infra/ directory pulling from pki/root/certs/ca.crt.