# DevSecOps, GitOps & Site Reliability Engineering (SRE) Assessment

**Project:** DevOps Task Board — Secure Delivery, Deployment, Observability & Reliability

## Overview

You have been assigned to deploy and manage **DevOps Task Board**, a lightweight Python web application. Users can create, view, complete, and delete tasks through a web interface and REST APIs. The application logs HTTP requests and exposes `/healthcheck` and `/readyz` endpoints.

Unlike the previous memory-leak application, DevOps Task Board stores tasks **in process memory**. This creates practical reliability challenges:

- Tasks disappear when the application process restarts.
- Each replica maintains a separate task list.
- A Service balancing requests across replicas can expose inconsistent data.
- Rolling updates and Pod failures can disrupt the user experience.

Your mission is to build a secure delivery pipeline, implement GitOps, identify and remediate the state-management problem, and add meaningful observability, scaling, and incident-response capabilities.

### Rules

- Use free/open-source tools, preferably locally with Minikube, Kind, or K3d. No paid cloud infrastructure is required.
- GitHub Actions and a free registry such as GHCR or Docker Hub are permitted.
- Application changes are allowed, but existing functionality must continue to work.
- Enforce security checks in CI/CD and implement Kubernetes runtime security controls.
- Version-control application code, Kubernetes manifests, pipeline configuration, and observability configuration.
- Document architecture, setup, reproduction, verification, and troubleshooting.
- Demonstrate working behavior; YAML files and tool installation alone are not sufficient.

---

## Task 1: Dockerization & Secure CI/CD Pipeline

### 1.1 Dockerize the application

Create an optimized `Dockerfile` that:

1. Uses a suitable minimal Python image.
2. Minimizes image size and excludes unnecessary files with `.dockerignore`.
3. Runs as a non-root user.
4. Sends logs to stdout/stderr.
5. Exposes port `8080` and serves both the frontend and REST APIs.

**Validation:**

```bash
docker build -t devops-task-board:v1 .
docker run -d --name task-board -p 8080:8080 devops-task-board:v1
curl http://localhost:8080/healthcheck
curl http://localhost:8080/api/tasks
```

Create a task via the API and verify it appears in the dashboard.

### 1.2 Multi-branch secure CI/CD architecture

**Branch protection:** Restrict direct changes to `main`; require Pull Requests and passing checks before merging. Store workflows in Git.

**Pull Request pipeline:** Trigger on PR open, synchronize, and reopen events targeting `main`. Include:

| Gate | Suggested tool | Acceptance criteria |
|---|---|---|
| Python linting | Flake8 / Ruff | No blocking lint errors |
| Unit tests | pytest | All tests pass |
| SAST | Bandit / Semgrep | No unresolved blocking findings |
| Secret scanning | Gitleaks (optional) | No exposed secrets |
| Image vulnerability scanning | Trivy | No unresolved vulnerabilities above the defined threshold |
| Container build | Docker Buildx | Build succeeds |
| API integration tests | pytest / curl | Core API operations work |

Findings specifically related to binding to `0.0.0.0` may be suppressed with documented justification. Do not indiscriminately disable other security checks.

Automated tests must verify:

- `/healthcheck` and `/readyz` return HTTP 200.
- Task listing returns valid JSON.
- Tasks can be created, completed, and deleted.
- Invalid inputs are rejected.
- Nonexistent tasks return appropriate errors.

**Validation challenge:** Introduce a failing test or lint violation in a PR. Show that merge is blocked until the issue is fixed.

### 1.3 Release pipeline (`main`)

After an approved PR is merged:

1. Build the production image.
2. Tag it uniquely, such as with the commit SHA.
3. Push it to GHCR or Docker Hub.
4. Update the Kubernetes GitOps manifest with the new image reference.
5. Commit the update through an approved automation identity or automated PR.
6. Allow Argo CD to synchronize the release.

Do not deploy mutable `latest` tags. If `main` is protected, use an automated PR or separate protected GitOps branch/repository rather than bypassing protection.

**Deliverable:** Successful security gates, published versioned image, and automated GitOps manifest update.

---

## Task 2: GitOps Deployment with Argo CD

### 2.1 Cluster and Argo CD setup

1. Create a local Kubernetes cluster.
2. Install Argo CD.
3. Connect Argo CD to the GitOps repository.
4. Create an Argo CD Application targeting the manifests.
5. Enable automated synchronization, pruning, and self-healing where appropriate.

**Validation challenge:** Manually change a Deployment replica count and demonstrate that Argo CD detects drift and restores the Git-defined state.

### 2.2 Kubernetes application deployment

Create:

- Dedicated application namespace.
- Deployment with at least two replicas.
- ClusterIP Service and Ingress or suitable local access method.
- Resource requests and limits.
- Startup, readiness, and liveness probes.
- Rolling update configuration, labels, and annotations.

Suggested **initial** resource configuration (measure and justify final values):

```yaml
resources:
  requests:
    cpu: 50m
    memory: 64Mi
  limits:
    cpu: 250m
    memory: 256Mi
```

Use `/healthcheck` for liveness and `/readyz` for readiness. Later, when PostgreSQL is introduced, ensure readiness reflects whether task requests can be served.

### 2.3 Kubernetes security and operational controls

| Component | Requirement |
|---|---|
| Namespaces | Separate application and observability workloads |
| ConfigMaps | Non-sensitive application settings |
| Secrets | Meaningful credentials introduced with a database or integration |
| ServiceAccounts | Dedicated identity; disable token automount unless required |
| RBAC | Least-privilege access for users or workloads that need Kubernetes API access |
| NetworkPolicies | Restrict unnecessary ingress and egress |
| ResourceQuotas | Limit namespace resource consumption |
| LimitRanges | Set default/minimum/maximum resource policies |
| initContainers | Perform a meaningful prerequisite check or initialization |
| SecurityContext | Non-root, drop unnecessary capabilities, no privilege escalation |

Do not introduce artificial permissions or dependencies solely to demonstrate a feature. NetworkPolicies require an enforcing CNI.

**Validation challenge:** Show allowed traffic, blocked cross-namespace traffic, non-root execution, denied unauthorized RBAC operations, and ResourceQuota enforcement.

---

## Task 3: Application State, Scaling & Reliability Engineering

**This replaces the previous memory-leak/OOMKilled task.**

### 3.1 Identify the state problem

Deploy one replica and create five tasks. Restart the Deployment:

```bash
kubectl rollout restart deployment/task-board -n task-board
```

Observe what happens to the tasks. Explain where they were stored, why a restart affects data, and how stateful and stateless services differ.

### 3.2 Demonstrate inconsistency across replicas

Scale to three replicas:

```bash
kubectl scale deployment/task-board --replicas=3 -n task-board
```

Create tasks and compare responses from different Pods (direct Pod access, port-forwarding, or repeated Service requests). Demonstrate that replicas can return different task lists. Explain why Kubernetes Services do not synchronize process memory.

**Before remediation:**

```text
Browser
   |
Kubernetes Service
   |---------|---------|
 App Pod 1  App Pod 2  App Pod 3
 Tasks A,B  Tasks C,D  Tasks E,F
 (separate in-memory state)
```

### 3.3 Implement persistent shared storage

**New requirement:** Tasks must survive Pod restarts, rolling deployments, and horizontal scaling.

Recommended solution: **PostgreSQL**.

Implement:

1. PostgreSQL with a StatefulSet or suitable local database deployment.
2. PersistentVolumeClaim-based storage.
3. Database Service.
4. ConfigMaps and Secrets for connection configuration.
5. Database schema initialization.
6. Application code changes to store tasks in PostgreSQL rather than Python memory.
7. Connection management and useful error handling.

**Target architecture:**

```text
Browser
   |
Kubernetes Service
   |---------|---------|
 App Pod 1  App Pod 2  App Pod 3
   |         |         |
   +---------+---------+
             |
     PostgreSQL Service
             |
      PostgreSQL + PVC
```

**Validation challenge:**

- Tasks survive application Pod restarts and rolling updates.
- All three replicas return consistent task data.
- Newly created tasks are visible through every replica.
- Readiness reflects inability to serve task requests when PostgreSQL is unavailable.
- Committed tasks are not lost during ordinary application restarts.

### 3.4 Rolling updates and rollback

Release a new version with a visible UI change. Verify image publication, GitOps manifest update, Argo CD sync, rolling deployment, availability, and preserved task data.

Then deploy a version with a failing readiness probe. Investigate the rollout and restore the previous healthy version by reverting the GitOps configuration.

**Deliverable:** Evidence of successful rollout, failed rollout detection, and recovery.

---

## Task 4: Observability, Logging & Alerting

### 4.1 Install the observability stack

Install via Helm where appropriate:

- Prometheus.
- Grafana.
- kube-state-metrics.
- Node Exporter.
- Loki with Grafana Alloy, or another supported central log collection solution.

### 4.2 Infrastructure dashboards

| Category | Metrics |
|---|---|
| Node | CPU, memory, disk usage |
| Kubernetes | Ready and unavailable Pods |
| Containers | CPU and memory per application Pod |
| Availability | Available replica count |
| Restarts | Container restart counts |
| Database | PostgreSQL availability and connection metrics, if instrumented |

**Validation:** Scale from one to three replicas and show replica counts, CPU/memory, and traffic distribution.

### 4.3 Application metrics

Instrument the Python application and expose a Prometheus-compatible `/metrics` endpoint.

| Metric | Purpose |
|---|---|
| `http_requests_total` | Requests by method, route, status |
| `http_request_duration_seconds` | Request latency |
| `task_operations_total` | Create, complete, delete operations |
| `task_operation_failures_total` | Failed operations |
| `database_connection_errors_total` | Database connectivity failures |

Configure scraping with a ServiceMonitor or equivalent. Avoid high-cardinality labels such as task IDs or raw URLs.

### 4.4 Centralized logging

Collect startup/shutdown, HTTP requests, task changes, errors, and database connection failures from every replica. Prefer structured JSON logs with timestamp, level, event, method, route, and status.

**Validation:** Generate successful and failed API requests, then retrieve corresponding logs centrally across replicas.

### 4.5 Grafana alerting

| Alert | Trigger | Validation |
|---|---|---|
| Application unavailable | No ready application replicas for a defined duration | Make all application Pods unready |
| High API error rate | 5xx ratio above threshold with enough traffic | Generate controlled server errors |
| High API latency | p95 latency above threshold | Introduce controlled delays |
| Database unavailable | Database health/connectivity fails | Stop database temporarily |
| Excessive restarts | Restart count rises above threshold | Simulate repeated crashes |

Use appropriate evaluation periods to reduce alert noise. Application instrumentation is required for latency and error-rate alerts.

**Bonus:** Deliver alerts to Slack, email, or a local webhook receiver.

**Validation:** Trigger at least three alert conditions; demonstrate firing, notification, and resolution.

---

## Task 5: Load Testing, Capacity Planning & Reliability

### 5.1 Establish a baseline

Use k6 or Locust to test task listing, creation, completion, and deletion. Measure throughput, average and p95 latency, error rate, CPU/memory, and database behavior with one application replica.

### 5.2 Compare horizontal scaling

Increase to three replicas and repeat the same load test. Investigate whether performance improves and whether the database becomes the bottleneck.

Answer:

- Does adding replicas always improve throughput?
- Can PostgreSQL become the bottleneck?
- What happens at the CPU limit?
- When does database connection pooling help?
- How does application scaling differ from database scaling?

### 5.3 Horizontal Pod Autoscaler

Configure CPU-based HPA, installing metrics-server if needed. Generate sustained load and demonstrate scale-out, Pod readiness, and scale-in.

If the app is too lightweight to trigger scaling, document this and use a controlled CPU-intensive test workload or application test mode.

### 5.4 SLOs and error budgets

Define and justify simple service-level objectives, for example:

- **Availability:** 99.9% of eligible requests succeed over a defined measurement period.
- **Latency:** 95% of eligible API requests complete within 500 ms.

Create Grafana panels for the corresponding SLIs. Explain error budgets and their impact on release decisions.

**Bonus:** Implement an SLO burn-rate alert.

---

## Task 6: Incident Response & Troubleshooting

Simulate and resolve the following incidents using Kubernetes events, application logs, metrics, and GitOps history.

| Incident | Simulation | Expected investigation |
|---|---|---|
| 1. Database unavailable | Temporarily stop PostgreSQL | Diagnose API/readiness impact and restore service |
| 2. Application crash loop | Introduce invalid startup configuration | Investigate `CrashLoopBackOff` and recover |
| 3. NetworkPolicy failure | Block application-to-database traffic | Find the restriction and implement minimal allow rule |
| 4. Failed deployment | Deploy a version with failing readiness | Investigate and revert GitOps release |
| 5. High latency | Introduce controlled task API delay | Detect increased p95 and resolve root cause |

For each incident, document symptoms, investigation, root cause, corrective action, and prevention.

---

## Task 7: Documentation & Final Demonstration

Submit a Git repository containing:

1. Application code and modifications.
2. Optimized Dockerfile and `.dockerignore`.
3. Unit and integration tests.
4. CI/CD workflows.
5. Kubernetes manifests or Helm/Kustomize configuration.
6. Argo CD Application configuration.
7. Database deployment and schema initialization.
8. Prometheus and Grafana setup.
9. Central logging configuration.
10. Grafana dashboards and alert rules.
11. Load-testing scripts.
12. Architecture diagrams.
13. Reproducible README.
14. Incident reports.

### Final demonstration workflow

```text
Developer Pull Request
        |
CI: Tests + Security Scanning
        |
Merge -> Build + Publish Image
        |
GitOps Manifest Update
        |
Argo CD Synchronization
        |
Kubernetes App + PostgreSQL
        |
Prometheus + Loki + Grafana
        |
Alerting + Incident Recovery
```

Demonstrate a code change progressing from PR to deployment, followed by a detected, investigated, and resolved application failure.

---

## Evaluation Criteria

| Area | Weight |
|---|---:|
| Dockerization and CI/CD security | 20% |
| Kubernetes and GitOps | 20% |
| Application state and persistence | 20% |
| Observability and alerting | 20% |
| Performance, scaling, and SRE | 10% |
| Troubleshooting and documentation | 10% |
| **Total** | **100%** |

### Minimum acceptance criteria

- [ ] CI blocks failing code or security checks.
- [ ] Merged PR builds and publishes a versioned image.
- [ ] Argo CD deploys new images automatically.
- [ ] Multiple replicas share persistent task data.
- [ ] Tasks survive application Pod restarts.
- [ ] Grafana shows real infrastructure and application metrics.
- [ ] Centralized logging works across replicas.
- [ ] At least three alerts are demonstrated.
- [ ] At least three incidents are diagnosed and resolved.
- [ ] The environment can be reproduced from documentation.

---

## Changes from the Previous Assessment

| Previous assessment | Revised assessment | Reason |
|---|---|---|
| Intentional memory leak | In-memory state inconsistency | Real limitation of new app |
| OOMKilled at `400Mi` | Data loss and consistency investigation | Relevant application behavior |
| Three image versions behind one Service | Multiple replicas of same release | Consistent application version |
| Memory-leak monitoring | API latency, errors, availability, DB health | User-facing reliability |
| Memory exhaustion alert | DB failures, crash loops, latency alerts | Realistic incidents |
| Pod restart observation | Persistence across restarts and rollouts | Data durability |
| Infrastructure-only monitoring | Infrastructure and application metrics | Better SRE coverage |
| No load testing | k6/Locust, HPA, capacity planning | Scalability engineering |

## Recommended Delivery Sequence

| Phase | Focus | Estimated effort |
|---|---|---|
| 1 | Docker and CI/CD | 2–3 days |
| 2 | Kubernetes and Argo CD | 2–3 days |
| 3 | PostgreSQL integration and persistence | 3–4 days |
| 4 | Observability and alerting | 3–4 days |
| 5 | Load testing and autoscaling | 1–2 days |
| 6 | Incidents and documentation | 2 days |

**Total:** Approximately **13–18 working days**, depending on experience.

### Assessment Design Note

**Task 3 — Application State, Scaling & Reliability Engineering** is the central architectural challenge. Learners must experimentally demonstrate a genuine defect, implement persistent shared state, and validate it through deployment and failure scenarios. PostgreSQL integration requires application-code changes; Kubernetes YAML alone cannot solve this problem. Allow sufficient time and appropriate Python database libraries.

