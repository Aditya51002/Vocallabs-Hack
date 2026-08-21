# AWS EC2 Hosting & Deployment Guide — ResearchSwarm

This guide provides step-by-step instructions for hosting **ResearchSwarm** on an AWS EC2 instance with automated Docker Hub image publishing and fast deployment via GitHub Actions.

---

## 1. AWS EC2 Instance Provisioning

### Recommended Specifications
- **AMI**: Ubuntu Server 24.04 LTS (64-bit x86) or Amazon Linux 2023.
- **Instance Type**: `t3.medium` (2 vCPU, 4 GiB RAM) or `t3.large` (recommended for multi-agent asynchronous swarms).
- **Storage**: Minimum 20 GB gp3 SSD.
- **Network**: Assign Public IPv4 or allocate an **Elastic IP** (EIP).

---

## 2. Security Group Configuration

Configure your EC2 Security Group inbound rules as follows:

| Type | Protocol | Port Range | Source | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **SSH** | TCP | `22` | My IP or Anywhere (`0.0.0.0/0`) | Secure Terminal Access |
| **HTTP** | TCP | `80` | Anywhere (`0.0.0.0/0`) | Web Traffic |
| **HTTPS** | TCP | `443` | Anywhere (`0.0.0.0/0`) | Encrypted SSL Web Traffic |
| **Custom TCP** | TCP | `3000` | Anywhere (`0.0.0.0/0`) | Frontend React UI |
| **Custom TCP** | TCP | `8000` | Anywhere (`0.0.0.0/0`) | FastAPI Backend API |

---

## 3. Initializing the EC2 Instance

1. Connect to your EC2 instance via SSH:
   ```bash
   ssh -i /path/to/your-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
   ```

2. Download and run the automated setup script:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/<YOUR_USER>/researchswarm/main/scripts/ec2-setup.sh | bash
   ```
   *(Or clone the repository manually and run `./scripts/ec2-setup.sh`)*

3. Log out and reconnect to apply group permissions:
   ```bash
   exit
   ssh -i /path/to/your-key.pem ubuntu@<YOUR_EC2_PUBLIC_IP>
   ```

---

## 4. Configuring GitHub Actions Secrets

In your GitHub repository, navigate to **Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions** and add the following **8 secrets**:

| Secret Name | Value Description | Example |
| :--- | :--- | :--- |
| **`DOCKERHUB_USERNAME`** | Your Docker Hub Username | `myusername` |
| **`DOCKERHUB_TOKEN`** | Your Docker Hub Personal Access Token (or password) | `dckr_pat_...` |
| **`EC2_HOST`** | Public IP or Elastic IP of your EC2 instance | `54.210.12.34` |
| **`EC2_USERNAME`** | SSH username | `ubuntu` (or `ec2-user`) |
| **`EC2_SSH_KEY`** | Entire content of your `.pem` private SSH key file | `-----BEGIN RSA PRIVATE KEY----- ...` |
| **`GROQ_API_KEY`** | Groq API Key | `gsk_...` |
| **`GEMINI_API_KEY`** | Gemini API Key | `AIzaSy...` |
| **`TAVILY_API_KEY`** | Tavily Web Search API Key | `tvly-...` |

---

## 5. Automated CI/CD Workflow

Once GitHub secrets are saved:
1. Every **Pull Request** will automatically run pytest backend tests, TypeScript build validation, and container builds.
2. Every **Push / Merge to `main`**:
   - Builds backend and frontend production images.
   - Pushes both images to **Docker Hub**: `${DOCKERHUB_USERNAME}/researchswarm-backend:latest` & `${DOCKERHUB_USERNAME}/researchswarm-frontend:latest`.
   - SSHs into EC2, pulls the pre-built images from Docker Hub, and restarts the containers using `docker compose pull && docker compose up -d`.

---

## 6. Accessing & Verifying the Application

After deployment:
- **Frontend Dashboard**: `http://<YOUR_EC2_PUBLIC_IP>:3000`
- **Backend API Health**: `http://<YOUR_EC2_PUBLIC_IP>:8000/api/health`
- **Swagger Docs**: `http://<YOUR_EC2_PUBLIC_IP>:8000/docs`

---

## 7. Useful Operational Commands on EC2

```bash
# View live container logs
docker compose logs -f

# Check container health status
docker compose ps

# Pull updated images from Docker Hub manually
docker compose pull

# Manually restart services
docker compose restart

# Stop all services
docker compose down
```
