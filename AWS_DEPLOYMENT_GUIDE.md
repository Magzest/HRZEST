# ☁️ AWS Deployment Guide — HRMS Employee Attendance Platform

This guide provides step-by-step instructions for hosting the platform on **AWS EC2** (recommended for full control and lowest cost) or **AWS Elastic Beanstalk / App Runner**.

---

## 🚀 Option 1: AWS EC2 (Recommended)

### Step 1: Launch an EC2 Instance
1. Open the [AWS EC2 Console](https://console.aws.amazon.com/ec2/).
2. Click **Launch Instance**:
   - **Name:** `hrms-attendance-server`
   - **AMI:** Ubuntu 24.04 LTS or 22.04 LTS (64-bit x86)
   - **Instance Type:** `t3.small` (2 vCPU, 2 GB RAM) or `t3.medium` (4 GB RAM for heavy face-recognition workloads)
   - **Key Pair:** Create or select an existing SSH key pair (`.pem`)
3. **Network Settings (Security Group):**
   - Allow **SSH (Port 22)** from your IP
   - Allow **HTTP (Port 80)** from Anywhere (`0.0.0.0/0`)
   - Allow **HTTPS (Port 443)** from Anywhere (`0.0.0.0/0`)
4. **Storage:** 20 GB gp3 SSD.
5. Click **Launch Instance**.

---

### Step 2: Connect to your EC2 Instance
```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<YOUR-EC2-PUBLIC-IP>
```

---

### Step 3: Install Docker & Dependencies
Run these commands inside your EC2 terminal:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-v2 git python3-pip python3-venv

# Enable Docker without sudo
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
newgrp docker
```

---

### Step 4: Clone & Configure Platform
```bash
git clone https://github.com/Nithin-magzest/emplyeee-attendance.git
cd emplyeee-attendance

# Run automatic environment key generator
python3 setup_env.py
```

Edit your `.env` file to set your domain and office GPS coordinates:
```bash
nano .env
```
Fill in:
```env
APP_ENV=production
APP_URL=https://yourdomain.com
OFFICE_LAT=28.6139   # Your office coordinates
OFFICE_LON=77.2090
ALLOWED_ORIGINS=https://yourdomain.com
```

---

### Step 5: Launch Containerized Stack
```bash
bash deploy.sh
```
Or manually with Docker Compose:
```bash
docker compose up --build -d
```

Verify status:
```bash
curl http://localhost:5000/healthz
# Expected: {"db":"connected","status":"ok"}
```

---

### Step 6: Enable HTTPS with Free SSL (Nginx + Certbot)
```bash
sudo apt install -y nginx certbot python3-certbot-nginx

# Copy provided Nginx configuration
sudo cp nginx.conf /etc/nginx/sites-available/attendance
sudo ln -s /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx config
sudo nginx -t
sudo systemctl reload nginx

# Issue free SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

---

## ⚡ Option 2: AWS App Runner (Zero Infrastructure Management)

If you don't want to manage Linux servers:

1. Push your Docker image to **AWS ECR** (Elastic Container Registry):
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   docker build -t hrms-attendance .
   docker tag hrms-attendance:latest <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/hrms-attendance:latest
   docker push <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/hrms-attendance:latest
   ```
2. Go to **AWS App Runner** console $\rightarrow$ Create Service.
3. Select your ECR repository and set port to `5000`.
4. Add environment variables (`SECRET_KEY`, `ENCRYPTION_KEY`, `APP_ENV=production`).
5. Click **Create & Deploy**.

---

## 📊 Summary Checklist for AWS

| Task | Command / Action |
|---|---|
| 1. Launch EC2 | `t3.small` (Ubuntu 24.04 LTS) |
| 2. Security Group | Open ports `22`, `80`, `443` |
| 3. Clone Repo | `git clone https://github.com/Nithin-magzest/emplyeee-attendance.git` |
| 4. Generate Keys | `python3 setup_env.py` |
| 5. Launch | `bash deploy.sh` |
| 6. Setup SSL | `sudo certbot --nginx -d yourdomain.com` |
