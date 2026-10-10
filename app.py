import json
import re
import requests
import streamlit as st
from google import genai
from google.genai import types
from supabase import create_client

# Fetch secrets from .streamlit/secrets.toml
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
N8N_WEBHOOK_URL = st.secrets.get("N8N_WEBHOOK_URL")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

st.set_page_config(page_title="LinkedIn Hook Grader", page_icon="⚡", layout="centered")

if "user_registered" not in st.session_state:
    st.session_state.user_registered = False

st.title("⚡ Enterprise LinkedIn Hook Grader")
st.markdown("Get a deterministic 5-rule score and 3 high-converting B2B rewrites.")

# --- SCREEN 1: CONTACT FORM GATE ---
if not st.session_state.user_registered:
    st.subheader("Step 1: Enter your details to unlock the tool")
    with st.form("contact_form"):
        name = st.text_input("Full Name")
        designation = st.text_input("Designation / Role")
        email = st.text_input("Email Address")
        submitted = st.form_submit_button("Unlock Tool 🚀")
        
        if submitted:
            if name and designation and email:
                st.session_state.user = {"name": name, "designation": designation, "email": email}
                st.session_state.user_registered = True
                st.rerun()
            else:
                st.error("Please complete all fields.")
else:
    # --- SCREEN 2: HOOK GRADER & REWRITER ---
    user = st.session_state.user
    
    col_welcome, col_back = st.columns([3, 1])
    with col_welcome:
        st.success(f"User: **{user['name']}** | Role: **{user['designation']}**")
    with col_back:
        if st.button("⬅️ Change Details"):
            st.session_state.user_registered = False
            st.rerun()

    hook_input = st.text_area("Paste your LinkedIn Hook (first 2 lines):", placeholder="e.g., 80% of enterprise tech implementations fail because...")

    if st.button("Grade & Rewrite Hook"):
        clean_hook = hook_input.strip()
        if not clean_hook:
            st.warning("Please enter a hook.")
        else:
            with st.spinner("Executing rule engine and requesting structured AI rewrites..."):
                
                # -------------------------------------------------------------
                # 1. DETERMINISTIC PYTHON SCORING ENGINE (5 RULES = 100 PTS)
                # -------------------------------------------------------------
                score = 100
                failures = []
                is_unprofessional = False

                # Rule 1: Character Length Check (20 pts)
                if len(clean_hook) < 40:
                    score -= 20
                    failures.append("❌ Too Short (-20 pts): Under 40 characters. Lacks context to build curiosity.")
                elif len(clean_hook) > 130:
                    score -= 20
                    failures.append("❌ Too Long (-20 pts): Over 130 characters. Will be truncated by LinkedIn UI.")

                # Rule 2: Curiosity & Engagement Triggers (20 pts)
                power_words = ["how", "why", "secret", "never", "stop", "mistake", "truth", "framework", "lessons", "tips", "guide", "reasons"]
                if not any(word in clean_hook.lower() for word in power_words):
                    score -= 20
                    failures.append("❌ Missing Curiosity Gap (-20 pts): Add a power word (e.g., How, Why, Mistake, Framework).")

                # Rule 3: Quantification & Specific Metrics (20 pts)
                has_digits = any(char.isdigit() for char in clean_hook)
                has_metrics = any(symbol in clean_hook for symbol in ["%", "$", "k", "M", "x", "£", "€"])
                if not (has_digits or has_metrics):
                    score -= 20
                    failures.append("❌ Lacks Specificity (-20 pts): Include a number, metric, or dollar amount.")

                # Rule 4: Formatting & Punctuation Integrity (20 pts)
                has_valid_ending = clean_hook.endswith(("?", ":", "!", "..."))
                has_bad_spacing = bool(re.search(r'\s+[?:!]', clean_hook))
                shouting = sum(1 for w in clean_hook.split() if w.isupper() and len(w) > 1) > 2

                if not has_valid_ending or has_bad_spacing or shouting:
                    score -= 20
                    failures.append("❌ Formatting / Grammar Penalty (-20 pts): Fix punctuation spacing (e.g., 'word ?'), avoid ALL-CAPS, and end with '?', ':', or '!'.")

                # Rule 5: Professionalism & Anti-Tone Guardrail (20 pts + Hard Cap)
                unprofessional_phrases = [
                    "awesome manager", "look at me", "i am the best", "hire me", "why me always", 
                    "suffering from success", "party than work", "never work seriously", "handsome", "greatest", "criminal"
                ]
                has_repeated_chars = bool(re.search(r'(.)\1{4,}', clean_hook))
                has_unprofessional_tone = any(phrase in clean_hook.lower() for phrase in unprofessional_phrases)

                if has_unprofessional_tone or has_repeated_chars:
                    is_unprofessional = True
                    score -= 20
                    failures.append("❌ Unprofessional / Informal Tone (-20 pts): Contains informal complaining, self-brags, or spam phrasing.")
                    # Zero-Tolerance Ceiling Cap
                    score = min(score, 30)

                score = max(0, score)

                # -------------------------------------------------------------
                # 2. STRUCTURED GEMINI AI REWRITES (SUPPRESSED IF UNPROFESSIONAL)
                # -------------------------------------------------------------
                rewrites = []
                
                if not is_unprofessional:
                    prompt = f"""
                    You are an elite B2B LinkedIn Copywriter and Personal Branding Strategist.

                    Transform this raw hook into 3 high-converting B2B rewrites for a user with role '{user['designation']}':
                    "{clean_hook}"

                    Strict Copywriting Rules:
                    1. Reframe informal or weak wording into authoritative B2B language focused on enterprise value, leadership, or execution.
                    2. DO NOT hallucinate fake dollar amounts or unprovided metrics (e.g., do not invent "$3.25M ARR" unless mentioned).
                    3. Ensure every rewrite creates an irresistible open loop above LinkedIn's 'see more' fold.

                    Return structured JSON with exactly 3 items.
                    """

                    candidate_models = ['gemini-flash-latest', 'gemini-3.5-flash-lite', 'gemini-2.5-flash']
                    response = None

                    for model_name in candidate_models:
                        try:
                            response = client.models.generate_content(
                                model=model_name,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema={
                                        "type": "OBJECT",
                                        "properties": {
                                            "rewrites": {
                                                "type": "ARRAY",
                                                "items": {
                                                    "type": "OBJECT",
                                                    "properties": {
                                                        "hook_style": {"type": "STRING"},
                                                        "rewritten_hook": {"type": "STRING"}
                                                    },
                                                    "required": ["hook_style", "rewritten_hook"]
                                                }
                                            }
                                        },
                                        "required": ["rewrites"]
                                    },
                                ),
                            )
                            if response and response.text:
                                break
                        except Exception:
                            continue

                    if response and response.text:
                        result_data = json.loads(response.text)
                        raw_rewrites = result_data.get("rewrites", [])
                        rewrites = raw_rewrites[:3]  # Strictly cap at 3

                # -------------------------------------------------------------
                # 3. OUTPUT DISPLAY
                # -------------------------------------------------------------
                st.divider()
                st.subheader(f"Deterministic Score: {score} / 100")

                if is_unprofessional:
                    st.error("🚨 **UNPROFESSIONAL CONTENT PENALTY**: Hook breaches workplace standards and is capped at 30/100 max. Rewrites suppressed.")

                if failures:
                    st.markdown("**Rule Deductions:**")
                    for f in failures:
                        st.markdown(f)
                else:
                    st.markdown("✅ **Flawless deterministic structure!**")

                if rewrites:
                    st.subheader("💡 3 High-Converting B2B Rewrites")
                    for idx, rw in enumerate(rewrites, 1):
                        st.info(f"**Option {idx} ({rw['hook_style']}):**\n\n{rw['rewritten_hook']}")

                # -------------------------------------------------------------
                # 4. DATA PERSISTENCE & WEBHOOK DISPATCH
                # -------------------------------------------------------------
                payload = {
                    "name": user['name'],
                    "designation": user['designation'],
                    "email": user['email'],
                    "hook": clean_hook,
                    "score": score,
                    "failures": "\n".join(failures) if failures else "None",
                    "rewrites": json.dumps(rewrites)  # Guaranteed array <= 3 items
                }

                # Supabase Storage
                try:
                    supabase.table("linkedin_hooks").insert(payload).execute()
                except Exception as e:
                    st.error(f"Supabase error: {e}")

                # Make.com / n8n Webhook Trigger
                try:
                    requests.post(N8N_WEBHOOK_URL, json=payload, timeout=5)
                except Exception:
                    pass