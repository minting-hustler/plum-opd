# Plum OPD Claim Adjudication Tool

AI-powered OPD insurance claim adjudication system built for the Plum internship assignment. Accepts medical documents, extracts structured data via Google Gemini, runs RAG-grounded rule-based adjudication against policy terms, and returns approve/reject/partial/manual-review decisions with confidence scores.

**Live demo**: https://plum-opd.vercel.app  
**API**: https://plum-opd-api.onrender.com/docs

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  React + Vite (Vercel)           │  Python FastAPI (Render)       │
│                                  │                                │
│  /login  /signup                 │  POST /documents/upload        │
│  /dashboard  ─── GET /claims ───▶│  POST /claims                  │
│  /claims/new ─── POST /upload ──▶│  POST /claims/{id}/adjudicate  │
│  /claims/:id ─── GET result ───▶ │  PATCH /claims/{id}/override   │
│  /admin                          │                                │
└──────────────────────────────────┼────────────────────────────────┘
                                   │
          ┌────────────────────────┼─────────────────────────┐
          │                        │                          │
    Firebase Auth           Firebase Firestore          Firebase Storage
    (email/password)        (claims, members,          (uploaded documents)
                            extracted_data,
                            adjudication_results)
          │
    Gemini 1.5 Flash                               Pinecone
    (document extraction,               (RAG: policy, medical,
     coverage check,                     past claims namespaces)
     medical necessity,
     reasoning)
```

### RAG Pipeline

Instead of sending the full policy document to Gemini on every call, each adjudication step queries Pinecone for the most relevant policy chunks (~500-1000 tokens vs ~15K tokens). This cuts token usage by ~90% and keeps us within the free tier.

Three Pinecone namespaces:
- `policy` — chunks from `policy_terms.json` + `adjudication_rules.md`
- `medical` — diagnosis → standard treatment guidelines
- `claims` — past adjudication decisions (grows with each processed claim)

---

## Adjudication Flow

```
Upload Documents ──▶ Gemini extracts structured data ──▶ Store in Firestore
                                                               │
Submit Claim ──▶ POST /claims/{id}/adjudicate ─────────────────▼
                                                    
Step 1: Eligibility (pure rule)
  └─ Policy active? Member covered? Waiting period elapsed?

Step 2: Document Validation (rule + RAG)
  └─ Legibility ≥ 0.5? Valid doctor reg#? Dates match? Patient name match?

Step 3: Coverage Verification (RAG → Gemini)
  └─ Retrieve policy clauses → Gemini determines covered/excluded items

Step 4: Limit Calculation (pure arithmetic)
  └─ Sub-limit check → Per-claim cap (₹5,000) → Annual cap (₹50,000) → Co-pay → Network discount

Step 5: Medical Necessity + Fraud (RAG → Gemini + rules)
  └─ Retrieve medical guidelines → Gemini assesses necessity
  └─ Check past claims for anomalies → Flag fraud indicators

Final Gemini Reasoning Call
  └─ Retrieve relevant policy chunks → Generate human-readable explanation

Decision: APPROVED / REJECTED / PARTIAL / MANUAL_REVIEW
```

---

## Free Tech Stack

| Layer | Service | Free Tier |
|-------|---------|-----------|
| Frontend | React + Vite on **Vercel** | Unlimited for hobby projects |
| Backend | Python FastAPI on **Render** | 750 hrs/month |
| Database | **Firebase Firestore** | 1GB, 50K reads/day |
| File Storage | **Firebase Storage** | 5GB, 1GB/day download |
| Auth | **Firebase Authentication** | Unlimited users |
| AI/LLM | **Google Gemini 1.5 Flash** | 15 RPM, 1M tokens/day |
| Embeddings | **Gemini embedding-004** | Same API key |
| Vector DB | **Pinecone** free tier | 1 index, 100K vectors |

---

## Setup Instructions

### Prerequisites
- Node.js 22.x
- Python 3.11+
- Accounts: Firebase, Pinecone, Google AI Studio, Render, Vercel

### 1. Firebase Setup
1. Go to [console.firebase.google.com](https://console.firebase.google.com) → Create project
2. Enable **Firestore** (production mode), **Storage**, **Authentication** (Email/Password)
3. Project Settings → Service Accounts → **Generate new private key**
4. Save the downloaded JSON as `backend/firebase-service-account.json`
5. In Authentication → Settings, set the storage rules to allow authenticated uploads

### 2. Pinecone Setup
1. Sign up at [pinecone.io](https://pinecone.io) (free tier)
2. Create an index: name=`plum-opd`, dimensions=`768`, metric=`cosine`
3. Copy your API key

### 3. Google AI Studio (Gemini API Key)
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API key** → Create API key
3. No credit card required

### 4. Backend (local)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Fill in: GEMINI_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME
# FIREBASE_SERVICE_ACCOUNT: paste the contents of firebase-service-account.json as a JSON string
# ALLOWED_ORIGINS=http://localhost:5173

uvicorn main:app --reload
# API docs available at http://localhost:8000/docs
```

### 5. Frontend (local)
```bash
cd frontend
npm install
cp .env.example .env
# Fill in VITE_API_URL=http://localhost:8000
# Fill in all VITE_FIREBASE_* values from Firebase console → Project Settings → Your apps → Web app

npm run dev
# App available at http://localhost:5173
```

### 6. Deploy to Render (backend)
1. Push this repo to GitHub
2. render.com → New Web Service → connect repo → select `backend/` folder
3. Runtime: **Python 3.11**, Build: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `GEMINI_API_KEY`
   - `PINECONE_API_KEY`
   - `PINECONE_INDEX_NAME=plum-opd`
   - `FIREBASE_SERVICE_ACCOUNT` (paste full JSON string)
   - `ALLOWED_ORIGINS=https://your-app.vercel.app`
6. Deploy and note the Render URL

### 7. Deploy to Vercel (frontend)
1. vercel.com → Import project → select `frontend/` folder → Framework: **Vite**
2. Add environment variables (all `VITE_*` values + `VITE_API_URL=https://your-render-url`)
3. Deploy

---

## API Documentation

Full interactive docs at `https://your-backend.onrender.com/docs` (auto-generated by FastAPI).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (pre-warms Render) |
| POST | `/members` | Create member profile |
| GET | `/members/{id}` | Get member + YTD usage |
| GET | `/members/by-uid/{uid}` | Get member by Firebase UID |
| POST | `/documents/upload` | Upload document, extract with Gemini |
| POST | `/claims` | Create claim |
| GET | `/claims` | List claims |
| GET | `/claims/{id}` | Get claim + adjudication result |
| POST | `/claims/{id}/adjudicate` | Run 5-step adjudication |
| PATCH | `/claims/{id}/override` | Admin override (MANUAL_REVIEW only) |

---

## Assumptions Made

1. **Doctor registration number format**: Regex validates allopathic format (`XX/NNNNN/YYYY`). Non-standard formats (Ayurveda, Homeopathy) are accepted with a warning — benefit of the doubt.

2. **Waiting period detection**: Keyword-based on extracted diagnosis strings. Conservative: "diabetic", "diabetes", "type 2" all trigger the 90-day wait. In production, ICD codes would be more reliable.

3. **Multi-document date conflicts**: If prescription date and bill date differ, prescription date is treated as authoritative for the treatment date comparison.

4. **annual_used counter**: Initialized to 0 for new members (demo assumption). Production would seed from historical data.

5. **Medical knowledge base**: Handcrafted JSON with ~30 diagnosis → treatment mappings. Sufficient for demo coverage of the 10 test cases. Production would use a licensed medical ontology or ICD coding.

6. **Past claims RAG namespace**: Seeded with the 10 test cases. The "similar claims" anomaly detection becomes more accurate as real claims accumulate.

7. **Render cold start**: Frontend calls `GET /health` on page load to pre-warm the Render instance (30s cold start after 15 min idle). During demo sessions, this won't be an issue.

8. **Currency**: All amounts in Indian Rupees (INR). Stored as integers (whole rupees, not paise).

9. **Pre-auth logic**: Only required for MRI and CT Scan. Detected from line item descriptions or test names in extracted data.

10. **Network hospital discount**: Applied only if `is_network=true` on the claim (self-declared by user at submission time). Production would verify against the network hospital list.

---

## Test Cases

The 10 test cases from `backend/data/seed_claims.json` cover all decision branches:

| Test | Scenario | Expected Decision |
|------|----------|-------------------|
| TC001 | Valid consultation with fever | APPROVED (₹1,350 after 10% copay) |
| TC002 | Dental: root canal + cosmetic whitening | PARTIAL (whitening excluded) |
| TC003 | Claim amount ₹7,500 > ₹5,000 per-claim limit | REJECTED: PER_CLAIM_EXCEEDED |
| TC004 | No prescription submitted | REJECTED: MISSING_DOCUMENTS |
| TC005 | Diabetes claim 45 days after join | REJECTED: WAITING_PERIOD |
| TC006 | Ayurvedic Panchakarma ₹4,000 | APPROVED |
| TC007 | MRI ₹15,000 without pre-auth | REJECTED: PRE_AUTH_MISSING |
| TC008 | 4 claims same day (fraud pattern) | MANUAL_REVIEW |
| TC009 | Weight loss / bariatric treatment | REJECTED: SERVICE_NOT_COVERED |
| TC010 | Apollo Hospitals (network) consultation | APPROVED (with 20% network discount) |
