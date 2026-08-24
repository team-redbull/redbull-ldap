# Deploying to OpenShift

The chart in [redbull-ldap/](redbull-ldap/) deploys the API and exposes it
through an OpenShift `Route`. It renders a Deployment, Service, Route,
ConfigMap, Secret and ServiceAccount - no operators or CRDs beyond `Route`.

## Build and push the image

The [Dockerfile](../Dockerfile) at the repo root builds it. Either build in the
cluster with a BuildConfig, or push from your machine:

```bash
oc new-project redbull-ldap                       # or use an existing one
podman build -t redbull-ldap:1.0.0 ..
podman push redbull-ldap:1.0.0 <registry>/<namespace>/redbull-ldap:1.0.0
```

## Install

Every connection detail is required - the chart refuses to render without
them, the same way the app refuses to start without them.

```bash
helm upgrade --install redbull-ldap ./redbull-ldap \
  --namespace redbull-ldap \
  --set image.repository=<registry>/<namespace>/redbull-ldap \
  --set image.tag=1.0.0 \
  --set config.ldapServer=ldaps://dc.example.internal \
  --set config.ldapDomain=YOURDOMAIN \
  --set config.adApiUrl=https://ad-api.example.internal/users/user/isUserMemberOfSecurityGroup \
  --set secret.adApiClientId=<client-id>
```

Keep the client id out of git. Either pass it on the command line as above, or
create the Secret yourself and point the chart at it:

```bash
oc create secret generic ad-api-creds --from-literal=AD_API_CLIENT_ID=<client-id>
helm upgrade --install redbull-ldap ./redbull-ldap ... --set secret.existingSecret=ad-api-creds
```

## After it is up

```bash
oc get route redbull-ldap -o jsonpath='{.spec.host}'
curl -s https://$(oc get route redbull-ldap -o jsonpath='{.spec.host}')/health
```

A CrashLoopBackOff straight after install almost always means a missing or
wrong setting: the app validates its environment at startup rather than on the
first request. `oc logs` will name the field.

## What the defaults assume

- **The Route terminates TLS at the router (`edge`) and redirects plain HTTP.**
  The pod speaks HTTP, so the unencrypted hop is router-to-pod inside the
  cluster. The service receives plaintext passwords in request bodies, so do
  not turn the redirect off.
- **`/auth` is a password-guessing oracle and the API has no authentication of
  its own.** A Route makes it reachable from outside the cluster. Add rate
  limiting (`route.annotations` has the router annotations commented out), or
  set `route.enabled=false` and let in-cluster callers use the Service.
- **The pods run under whatever UID the namespace's SCC assigns.** The chart
  sets no `runAsUser` or `fsGroup` on purpose - it is compatible with
  `restricted-v2` and hardcoding an id would break installs elsewhere.
- **Both probes hit `/health`**, which never touches LDAP or the AD API, so an
  upstream outage cannot get healthy pods killed or removed from the Service.

## Working on the chart

```bash
helm lint redbull-ldap -f redbull-ldap/ci/test-values.yaml
helm template rb redbull-ldap -f redbull-ldap/ci/test-values.yaml
```

`ci/test-values.yaml` exists only to satisfy the required values when
rendering; it is not a deployable configuration.
