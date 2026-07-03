# TODO

Planned work and follow-ups for the PKI manager.

## CRL Distribution Point (CDP) webserver — `certs.cybertron.corp`

Stand up a webserver at `certs.cybertron.corp` to publish the intermediate CA's
CRL (and, ideally, the CA chain) so that clients can automatically fetch
revocation information instead of relying on manual CRL distribution.

**Why:** Certificates issued today do not embed a CRL Distribution Point, so
revoking a cert (e.g. via `./pki-manager.sh revoke <service>`) has no effect on
clients unless the CRL is hand-delivered. A published CDP makes revocation
actually enforceable.

**Tasks:**
- [ ] Provision a host/service for `certs.cybertron.corp` (HTTP is fine and
      conventional for CRLs — the CRL is signed, so it does not require HTTPS).
- [ ] Add a DNS record for `certs.cybertron.corp`.
- [ ] Publish the intermediate CRL at a stable URL, e.g.
      `http://certs.cybertron.corp/crl/intermediate.crl`.
      - Copy `pki/intermediate/crl/intermediate_ca.crl` there after each
        `revoke` / `gen-crl` run.
- [ ] Optionally publish the CA chain / root cert for download at the same host,
      e.g. `http://certs.cybertron.corp/certs/ca-chain.crt`.
- [ ] Add a `crlDistributionPoints` extension to the leaf cert profiles in
      `openssl.conf` so newly issued certs point at the CDP URL, e.g.:

      ```
      crlDistributionPoints = URI:http://certs.cybertron.corp/crl/intermediate.crl
      ```

      Add this to the `[ server_cert ]`, `[ client_cert ]`, and
      `[ server_san_cert ]` (temp config) profiles.
- [ ] Consider adding `authorityInfoAccess` (AIA) pointing at the CA cert URL.
- [ ] Automate CRL refresh + publish (CRL expires per `default_crl_days = 30`;
      it must be regenerated and re-published before `Next Update` passes, even
      if nothing new was revoked). A cron job running `gen-crl` + copy is enough.
- [ ] Note: existing certs (issued before the CDP exists) will not gain a CDP
      retroactively — they would need to be reissued to benefit.
