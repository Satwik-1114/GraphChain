# 🧬 GraphChain — Federated Disease Intelligence System

> A privacy-preserving, blockchain-verified federated learning platform that enables hospitals and healthcare institutions to collaboratively train a global disease-symptom knowledge graph — **without sharing raw patient data**.
LIVE LINK:https://graph-chain.vercel.app/
---
## 📌 Overview

**GraphChain** combines three powerful technologies:

| Technology | Role |
|---|---|
| **Federated Learning** | Trains a global model by aggregating local hospital models |
| **Neo4j (Graph Database)** | Stores and queries the global disease-symptom knowledge graph |
| **Blockchain (Ethereum/Sepolia)** | Tamper-proof verification of the global model hash |

Each hospital uploads its local patient data (CSV), which is converted into a **local disease-symptom graph**. The system owner triggers **Federated Averaging** across all approved participants, producing a **Global Knowledge Graph** that is:
- Stored in **Neo4j**
- Cryptographically hashed and verified against the **Ethereum blockchain**
- Visualized in an interactive dashboard using **Plotly**

---

## 🏗️ Project Structure

```
federated_app/
│
├── app.py                      # Entry point — registers all blueprints
├── config.py                   # Loads environment variables via python-dotenv
├── extensions.py               # Flask app, MongoDB client, LoginManager, User model
│
├── graph_utils.py              # Core graph logic:
│                               #   - CSV → NetworkX graph
│                               #   - Federated averaging
│                               #   - Plotly visualization
│                               #   - Local vs Global comparison
│
├── neo4j_utils.py              # Neo4j driver + graph push/fetch/cycle functions
├── blockchain_utils.py         # Web3 connection + contract hash verification
│
├── routes/
│   ├── __init__.py
│   ├── auth.py                 # Login, signup, logout
│   ├── dashboard.py            # Main dashboard + upload + federate + push
│   ├── participants.py         # Owner: approve / remove participants
│   └── api.py                  # REST endpoints for hashes and user status
│
├── templates/
│   ├── index.html              # Landing page
│   ├── login.html              # Login form
│   ├── signup.html             # Signup form
│   ├── dashboard.html          # Main user dashboard
│   └── approve_participants.html  # Owner participant management
│
├── uploads/                    # Temporary CSV uploads (gitignored)
├── blockchain/
│   └── FederatedIntegrity.json # Compiled Solidity ABI artifact
│
├── .env                        # 🔒 Secret credentials (gitignored)
├── .env.example                # Template for .env setup
├── .gitignore
└── requirements.txt
```

---

## 👥 User Roles

| Role | Capabilities |
|---|---|
| **Observer** | Can view the landing page, register, and request participation |
| **Participant** | Can upload CSV datasets and view local + global graphs |
| **Owner** | Can approve/remove participants, trigger federated aggregation, and push global model to Neo4j |

---

## 🔄 Workflow

```
1. Hospital registers → requests participation (submits wallet address)
        ↓
2. Owner approves the hospital as a Participant
        ↓
3. Participant uploads a patient CSV file
   → Parsed into a local disease-symptom graph (NetworkX)
   → Learning model (probabilities + symptom strengths) stored in MongoDB
        ↓
4. Owner triggers Federated Averaging
   → Averages all approved participants' local models
   → Generates SHA-256 hash of the global model
   → Stores result in MongoDB as a PENDING global model
        ↓
5. Owner signs the global model hash on-chain (MetaMask / Ethereum)
        ↓
6. Owner confirms → global model pushed to Neo4j
   → Blockchain hash verified against Neo4j hash
   → Dashboard shows ✅ VERIFIED global graph
        ↓
7. All participants can see:
   - Their local graph vs global graph
   - Newly discovered diseases/symptoms (highlighted in green)
```

---

## 🗄️ Data Storage

| Store | What's Stored |
|---|---|
| **MongoDB** | Users, local models (edges, adjacency matrix, hash), pending global models |
| **Neo4j** | Verified global federated graph (FederatedModel → Disease → Symptom) |
| **Blockchain** | SHA-256 hash of the global model (immutable, tamper-proof) |

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Satwik-1114/GraphChain.git
cd GraphChain
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
# Flask
SECRET_KEY=your_flask_secret_key

# MongoDB
MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/<db>?retryWrites=true&w=majority
MONGO_DB_NAME=federated_db

# Neo4j
NEO4J_URI=neo4j+ssc://<instance>.databases.neo4j.io
NEO4J_USERNAME=<username>
NEO4J_PASSWORD=<password>

# Blockchain (Infura / Sepolia Testnet)
INFURA_URL=https://sepolia.infura.io/v3/<project_id>
CONTRACT_ADDRESS=0xYourContractAddress
```

### 5. Run the Application

```bash
python app.py
```

Visit **http://127.0.0.1:5000** in your browser.

---

## 📊 CSV Format

Participant hospitals upload CSV files in the following format:

```csv
patient_id,diagnosis,symptom1,symptom2,symptom3
P001,Flu,Fever,Cough,Fatigue
P002,Malaria,Fever,Chills,Sweating
P003,Flu,Fever,Sore Throat,
```

- `patient_id` — unique patient identifier (not used in graph)
- `diagnosis` — disease label (graph node)
- `symptom1`, `symptom2`, ... — symptom columns (graph nodes connected to disease)

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/get_user_status` | Returns current user's role and approval status |
| `GET` | `/get_pending_count` | Returns number of pending participant requests |
| `GET` | `/get_local_hash` | Returns SHA-256 hash of current user's local model |
| `GET` | `/get_global_hash` | Returns SHA-256 hash of the latest global model |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python, Flask, Flask-Login |
| **Graph Processing** | NetworkX, Pandas |
| **Visualization** | Plotly |
| **Primary Database** | MongoDB Atlas (via PyMongo) |
| **Graph Database** | Neo4j Aura |
| **Blockchain** | Ethereum Sepolia Testnet (via Web3.py + Infura) |
| **Smart Contract** | Solidity (`FederatedIntegrity.sol`) |
| **Config Management** | python-dotenv |

---

## 🔒 Security Notes

- Raw patient data is **never shared** — only aggregated model statistics leave the hospital
- All credentials are loaded from `.env` (never hardcoded)
- `.env` is listed in `.gitignore` and **never committed**
- Global model integrity is verified against an **immutable blockchain record**

---

## 📄 License

This project is for academic and research purposes.

---

> Built with ❤️ by [Satwik-1114](https://github.com/Satwik-1114)
