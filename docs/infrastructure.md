# Infrastructure (Google Cloud Run, OpenTofu)

Carpathian Keros runs on **Google Cloud Run** in `europe-west1`. All Google Cloud resources are defined as code with **OpenTofu** in `infra/`, apart from one documented manual step (the `.cloud.run` custom URL, below).

```
GitHub Actions (deploy.yml, on a v* tag)
   │  OIDC token ──▶ Workload Identity Federation ──▶ short-lived credentials as ck-deployer (no keys anywhere)
   ├─ docker push ──▶ Artifact Registry  europe-west1-docker.pkg.dev/<project>/carpathian-keros
   └─ deploy ───────▶ Cloud Run service carpathian-keros (runs as ck-runtime, which has no roles)
                         ├─ https://carpathian-keros-<project-number>.europe-west1.run.app   (default URL)
                         └─ https://carpathian-keros.cloud.run                               (custom URL, Preview)
```

> **Status:**
> - **Infrastructure:** applied, and `https://carpathian-keros.cloud.run` is claimed.
> - **Releases:** deployed by `.github/workflows/deploy.yml` (see [Deploying a release](#deploying-a-release)).
> - **Until the first `v*` tag:** the service runs Google's placeholder "hello" image.

## What's managed, and where

| File | Resources | Notes |
|---|---|---|
| `infra/bootstrap/` | GCS bucket `<project>-tfstate` for OpenTofu state, and the **foundation APIs** (Storage, Resource Manager, Service Usage) | Versioned, private (`public_access_prevention = enforced`), never force-destroyed. The APIs live here because `infra/` needs them while it *plans* |
| `infra/apis.tf` | Run, Artifact Registry, IAM, IAM Credentials, STS, Billing Budgets APIs | Never disabled on destroy |
| `infra/registry.tf` | Docker repository `carpathian-keros` | Immutable tags; keeps the 5 newest images and deletes older ones after 7 days (stays inside the 0.5 GB free storage); paid image scanning off (Trivy scans in CI) |
| `infra/iam.tf` | Service accounts `ck-runtime` (no roles) and `ck-deployer` | Every grant is **resource-scoped**: push to this repository, deploy this service, act as `ck-runtime`. No project-wide roles, no keys |
| `infra/wif.tf` | Workload Identity pool `github` + provider | Trusts **only** repository ID 1471744541 (owner 356566022), **only** the `deploy.yml` workflow, **only** on `main` or `v*` tags |
| `infra/run.tf` | Cloud Run service `carpathian-keros` + public invoker | Scale to zero, max 2 instances, 1 vCPU / 512 MiB, CPU only during requests, `/health` startup and liveness probes, deletion protection |
| `infra/budget.tf` | €1 monthly budget on this project | Emails billing admins at 50%, 90%, 100% and forecast 100%. Alerts only, never stops anything |

**OpenTofu owns the configuration; the deploy workflow owns the image version.** The service has `ignore_changes` on the container image, so a later `tofu apply` never rolls production back to the placeholder image (policy-tested).

## Free tier and cost

The setup is sized to stay inside Google Cloud's free tier for a personal project:
- **Cloud Run:** scales to zero (no idle cost) and allocates CPU only while handling requests. At most 2 instances.
- **Artifact Registry:** about 100 MB per image (compressed), at most 5 kept.
- **The state bucket:** a few KB.
- **Firebase, load balancers, image scanning:** not used.

Check Google's current pricing pages for the exact free allowances: [Cloud Run](https://cloud.google.com/run/pricing), [Artifact Registry](https://cloud.google.com/artifact-registry/pricing). The **€1 budget alert** is the safety net. If it ever emails you, look at *Billing → Reports* in the console.

## First-time setup

You run this once, from your own machine, with your own Google account (Owner of the project). After that, GitHub Actions deploys without any stored credentials.

**Prerequisites:**
- **Accounts:** a Google Cloud project with billing linked.
- **Tools in WSL:** `tofu` (OpenTofu ≥ 1.9) and `gcloud`.

### 1. Sign in

```bash
gcloud auth login                                    # for gcloud commands
gcloud auth application-default login                # credentials OpenTofu uses ("ADC")
gcloud auth application-default set-quota-project carpathian-keros   # bill API quota to your project
gcloud config set project carpathian-keros
gcloud billing projects describe carpathian-keros    # must show billingEnabled: True; note the billing account ID
```

### 2. Create the state bucket (bootstrap)

```bash
cd infra/bootstrap
tofu init
tofu apply -var="project_id=carpathian-keros"        # review the plan: 3 APIs + 1 bucket
```

Then move the bootstrap's own state into the bucket it just created, so nothing lives only on your laptop:

```bash
cat > backend.hcl <<'EOF'
bucket = "carpathian-keros-tfstate"
prefix = "bootstrap"
EOF
# In versions.tf, uncomment:  backend "gcs" {}
tofu init -backend-config=backend.hcl -migrate-state   # answer "yes"
rm terraform.tfstate terraform.tfstate.backup
```

(Committing that one-line `versions.tf` change afterwards is fine. `backend.hcl` stays git-ignored.)

### 3. Create everything else

```bash
cd ..                                   # infra/
cp backend.hcl.example backend.hcl      # bucket = "carpathian-keros-tfstate", prefix = "infra"
cp terraform.tfvars.example terraform.tfvars
#   project_id         = "carpathian-keros"
#   billing_account_id = "XXXXXX-XXXXXX-XXXXXX"   (from step 1)
tofu init -backend-config=backend.hcl
tofu plan -out=tfplan                   # read it: about 20 resources, nothing outside this project
tofu apply tfplan
tofu output                             # service_url, workload_identity_provider, deployer_service_account, image_repository, …
```

Open `service_url`: you should see Google's "It's running!" placeholder page, served over HTTPS.

### 4. Claim the custom URL `carpathian-keros.cloud.run` (manual, once)

Cloud Run's **custom URLs** give the service a clean address, `https://carpathian-keros.cloud.run`, with HTTPS and no DNS or domain to buy. This is the **one deliberate exception** to "everything in code":

- **No OpenTofu support:** Google states that *Terraform isn't supported for custom URLs* and advises against its Preview `domain_mapping` resource.
- **It needs `roles/run.admin`.** The deploy workflow's account intentionally doesn't have that, so the mapping can't be part of CD either. You create it once with your Owner account:

```bash
gcloud beta run domain-mappings create \
  --service=carpathian-keros --domain=carpathian-keros.cloud.run --region=europe-west1
gcloud beta run domain-mappings describe --domain=carpathian-keros.cloud.run --region=europe-west1
curl -sI https://carpathian-keros.cloud.run/health      # expect HTTP/2 200 after a few seconds
```

Things to know, from [Google's documentation](https://docs.cloud.google.com/run/docs/custom-urls):
- **It's a Preview feature** ("as is"; Google may change it, and "reserves the right to … revoke or reassign subdomains"). That's why the default `run.app` URL stays enabled as a fallback. The two work independently.
- **Names are first come, first served.** If `carpathian-keros` is taken, pick another name of 6–63 characters (letters, digits, hyphens).
- **Never delete the mapping casually:** the name becomes **immediately** available to anyone. Deleting the *service* doesn't release it.
- **It survives redeploys:** new revisions keep the URL; nothing in CD touches it.

If the command fails in `europe-west1` (Google's page doesn't list regions), the service keeps working on its `run.app` URL. Record the error in this file and in the "Current gaps" section of `AGENTS.md`.

### 5. Connect GitHub (for the deploy workflow)

In GitHub → **Settings → Secrets and variables → Actions → Variables**, create these from `tofu output`. They're **variables, not secrets**: none of them grants access on its own, because Workload Identity Federation checks the workflow's identity.

| Variable | From |
|---|---|
| `GCP_PROJECT_ID` | `carpathian-keros` |
| `GCP_REGION` | `europe-west1` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `tofu output -raw workload_identity_provider` |
| `GCP_DEPLOYER_SERVICE_ACCOUNT` | `tofu output -raw deployer_service_account` |
| `GCP_IMAGE_REPOSITORY` | `tofu output -raw image_repository` |
| `GCP_SERVICE_NAME` | `tofu output -raw service_name` |

## Deploying a release

Pushing a release tag deploys it: `git tag -a v1.1.0 -m "…" && git push origin v1.1.0`, on `main` after the release PR (AGENTS.md, Article VI). The workflow `.github/workflows/deploy.yml` (*Deploy to Cloud Run*) then:

1. **Checks the tag** against `version` in `pyproject.toml`, so `v1.1.0` can only deploy 1.1.0.
2. **Builds the image and scans it with Trivy.** A fixable HIGH/CRITICAL vulnerability stops the deploy before anything is pushed.
3. **Authenticates through Workload Identity Federation** and pushes `…/carpathian-keros/app:1.1.0`. Tags are immutable; a re-run reuses the pushed image.
4. **Deploys a candidate revision with no traffic**, tagged `candidate`. Users still see the previous version.
5. **Smoke-tests the candidate on its own URL** (`https://candidate---carpathian-keros-….run.app`) with `scripts/smoke_test.py`:
   - `/health` reports the expected version
   - the page loads with its security headers
   - the weather API works against live Open-Meteo
   - the PDF export works
6. **Promotes it** to 100% of the traffic.
7. **Verifies the public URL** `https://carpathian-keros.cloud.run` the same way. If that fails, the workflow **sends the traffic back** to the previous revision automatically.

Only the image changes in a deploy. Scaling, the service account and the probes stay exactly as OpenTofu defines them (`infra/run.tf` ignores just the image and the traffic split). The deployment shows up on the repository's **Environments → production** page, with a link to the URL.

**Run the smoke test yourself:** `python3 scripts/smoke_test.py https://carpathian-keros.cloud.run 1.1.0`

**Roll back by hand** to any earlier revision:
```bash
gcloud run revisions list --service=carpathian-keros --region=europe-west1          # newest first
gcloud run services update-traffic carpathian-keros --region=europe-west1 --to-revisions=<REVISION>=100
```

**Redeploy `main` without a new release** (e.g. after a rollback): *Actions → Deploy to Cloud Run → Run workflow* on `main`. The image is tagged `<version>-<commit>`.

## Changing the infrastructure

- **Edit `infra/*.tf` on an `infra/<description>` branch** (AGENTS.md, Article VI), with a test in `infra/tests/` for any new security or cost rule.
- **CI's *Infrastructure* job checks every PR:** `tofu fmt`, `validate`, `tofu test` (Google provider mocked: no credentials, nothing created), tflint with the Google ruleset, and Trivy's misconfiguration scan.
- **After merging, apply from your machine:** `tofu plan -out=tfplan && tofu apply tfplan` in `infra/`. **AI agents never run `apply` or `destroy`** (AGENTS.md).

Local equivalents of the CI checks:

```bash
cd infra
tofu fmt -check -recursive
for d in bootstrap .; do tofu -chdir=$d init -backend=false && tofu -chdir=$d validate && tofu -chdir=$d test; done
docker run --rm -v "$PWD:/data" -w /data -e TFLINT_PLUGIN_DIR=/data/.terraform/tflint-plugins ghcr.io/terraform-linters/tflint:v0.66.0 --init
docker run --rm -v "$PWD:/data" -w /data -e TFLINT_PLUGIN_DIR=/data/.terraform/tflint-plugins ghcr.io/terraform-linters/tflint:v0.66.0 --recursive --config=/data/.tflint.hcl
docker run --rm -v "$PWD:/src:ro" aquasec/trivy:0.76.2 config --skip-dirs .terraform --severity MEDIUM,HIGH,CRITICAL /src
```

## Tearing down

1. Delete the custom URL mapping only if you're giving up the name for good (see above).
2. In `infra/run.tf` set `deletion_protection = false`, then `tofu apply`, then `tofu destroy`.
3. The Workload Identity pool ID `github` stays reserved for 30 days after deletion; recreating it sooner fails.
4. The state bucket (bootstrap) has `force_destroy = false`. Empty it deliberately before destroying it.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `billingbudgets…: … requires a quota project` / 403 on the budget | Run `gcloud auth application-default set-quota-project carpathian-keros` (step 1) |
| Budget: `currency code … does not match` | Set `budget_currency` in `terraform.tfvars` to your billing account's currency (e.g. `RON`, `USD`) |
| `Error 409: … already exists` for `github` pool | A pool with that ID was deleted less than 30 days ago; wait or change the ID in `wif.tf` |
| First revision fails its startup probe | The placeholder image didn't answer `/health`. Set `initial_image` to a pushed Carpathian Keros image and apply again |
| A path works locally but returns Google's 404 on Cloud Run | It ends in `z` (e.g. `/healthz`): Cloud Run reserves such paths. Rename the route; that's why the health check is `/health` |
| `.cloud.run` mapping: name not available | Choose another name (6–63 characters). It's first come, first served |
| `infra/` plan: `Cloud Resource Manager API has not been used in project … (SERVICE_DISABLED)` | The bootstrap enables that API; apply (or re-apply) `infra/bootstrap` first, wait about a minute, then plan `infra/` again |
| `gcloud billing … describe` shows `billingEnabled: false` | No billing account linked. Create one (console → Billing) and `gcloud billing projects link <project> --billing-account=<ID>`. Cloud Run needs billing even within the free tier |
| `gcloud` returns 429 `RATE_LIMIT_EXCEEDED` on `cloudbilling` | Temporary limit on gcloud's shared client project; wait a minute. Setting the quota project (step 1) avoids it for OpenTofu |
