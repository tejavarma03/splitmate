"""
SplitMate - A Better Expense Splitting App
Built with Python & Streamlit
"""

import streamlit as st
import json
import datetime
import math
from collections import defaultdict
import hashlib
import os

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

# ─── CONFIG ───────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SplitMate",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── SESSION STATE ────────────────────────────────────────────────────────────

for key in ["group_form_key", "expense_form_key", "settle_form_key", "member_add_key"]:
    if key not in st.session_state:
        st.session_state[key] = 0
if "success_msg" not in st.session_state:
    st.session_state.success_msg = None
if "show_reset_confirm" not in st.session_state:
    st.session_state.show_reset_confirm = False
if "active_group" not in st.session_state:
    st.session_state.active_group = None

ADMIN_PASSWORD = "split1234"

# ─── CUSTOM CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    .stApp { font-family: 'Inter', sans-serif; }

    .hero {
        background: linear-gradient(135deg, #1DB954 0%, #0D9B3F 50%, #087A30 100%);
        padding: 2rem 2.5rem; border-radius: 20px; color: white;
        margin-bottom: 1.5rem; box-shadow: 0 8px 32px rgba(29, 185, 84, 0.25);
    }
    .hero h1 { margin: 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -1px; }
    .hero p { margin: 0.3rem 0 0; opacity: 0.85; font-size: 1rem; }

    .stat-card {
        background: white; border-radius: 16px; padding: 1.4rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06); border: 1px solid #f0f0f0;
        text-align: center; transition: transform 0.2s;
    }
    .stat-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.1); }
    .stat-label { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
    .stat-value { font-size: 1.8rem; font-weight: 800; margin: 0.3rem 0; }
    .stat-green { color: #1DB954; }
    .stat-red { color: #E74C3C; }
    .stat-blue { color: #3498DB; }
    .stat-purple { color: #9B59B6; }

    .expense-card {
        background: white; border-radius: 14px; padding: 1.1rem 1.3rem;
        margin-bottom: 0.7rem; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border-left: 4px solid #1DB954; display: flex;
        justify-content: space-between; align-items: center;
    }
    .expense-card .title { font-weight: 700; font-size: 1rem; color: #222; }
    .expense-card .meta { font-size: 0.78rem; color: #999; margin-top: 2px; }
    .expense-card .amount { font-size: 1.2rem; font-weight: 800; color: #1DB954; }

    .balance-pos {
        background: linear-gradient(135deg, #e8f9ef, #d4f5e0);
        border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 0.5rem;
        border-left: 4px solid #1DB954;
    }
    .balance-neg {
        background: linear-gradient(135deg, #fde8e8, #fbd4d4);
        border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 0.5rem;
        border-left: 4px solid #E74C3C;
    }

    .settle-row {
        background: #f8f9fa; border-radius: 12px; padding: 0.9rem 1.2rem;
        margin-bottom: 0.5rem; display: flex; align-items: center;
        gap: 0.8rem; font-size: 0.95rem;
    }
    .settle-arrow { font-size: 1.3rem; }

    .group-badge {
        display: inline-block; background: linear-gradient(135deg, #1DB954, #0D9B3F);
        color: white; padding: 0.3rem 0.9rem; border-radius: 20px;
        font-size: 0.8rem; font-weight: 600;
    }
    .group-badge-active {
        display: inline-block; background: linear-gradient(135deg, #E74C3C, #C0392B);
        color: white; padding: 0.3rem 0.9rem; border-radius: 20px;
        font-size: 0.8rem; font-weight: 600;
    }

    .member-chip {
        display: inline-flex; align-items: center; gap: 4px;
        background: #f0f0f0; padding: 3px 10px; border-radius: 16px;
        font-size: 0.8rem; margin: 2px 2px; font-weight: 500;
    }

    .activity-item {
        padding: 0.7rem 0; border-bottom: 1px solid #f0f0f0;
        font-size: 0.9rem; color: #555;
    }
    .activity-item:last-child { border-bottom: none; }
    .activity-time { font-size: 0.75rem; color: #bbb; }

    .stButton>button { border-radius: 12px; font-weight: 600; padding: 0.5rem 1.5rem; transition: all 0.2s; }

    div[data-testid="stSidebar"] { background: linear-gradient(180deg, #f8faf9 0%, #edf5f0 100%); }

    .success-toast {
        background: linear-gradient(135deg, #1DB954, #0D9B3F);
        color: white; padding: 1rem 1.5rem; border-radius: 12px;
        font-weight: 600; margin-bottom: 1rem;
        animation: fadeIn 0.3s ease-in;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
</style>
""", unsafe_allow_html=True)

# ─── DATA LAYER ───────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "splitmate_data.json")

SHEET_HEADERS = {
    "groups": ["group_name", "member_name", "color"],
    "expenses": ["id", "description", "amount", "category", "date", "paid_by", "group", "split_type", "participants", "split_details", "created_at"],
    "settlements": ["id", "from", "to", "amount", "date", "group", "created_at"],
    "activity_log": ["message", "time"],
}

CATEGORIES = {
    "🍔 Food & Drink": "#FF6B6B", "🏠 Housing": "#4ECDC4",
    "🚗 Transport": "#45B7D1", "🎬 Entertainment": "#96CEB4",
    "🛒 Shopping": "#FFEAA7", "✈️ Travel": "#DDA0DD",
    "💡 Utilities": "#98D8C8", "💊 Health": "#F7DC6F",
    "📚 Education": "#BB8FCE", "🎁 Gifts": "#F1948A",
    "📦 Other": "#AEB6BF",
}


def default_data():
    return {
        "groups": [{"name": "General", "members": ["You"], "color": "#1DB954"}],
        "expenses": [],
        "settlements": [],
        "activity_log": [],
    }


def normalize_data(data):
    """Keep old saved files compatible and make sure every record has a stable ID."""
    if not isinstance(data, dict):
        data = default_data()

    for k, v in default_data().items():
        if k not in data or data[k] is None:
            data[k] = v

    data.pop("members", None)
    data["groups"] = data.get("groups", []) or default_data()["groups"]
    data["expenses"] = data.get("expenses", []) or []
    data["settlements"] = data.get("settlements", []) or []
    data["activity_log"] = data.get("activity_log", []) or []

    next_exp_id = 1
    for exp in data["expenses"]:
        if "id" not in exp:
            exp["id"] = next_exp_id
        try:
            exp["amount"] = float(exp.get("amount", 0))
            next_exp_id = max(next_exp_id, int(exp.get("id", 0)) + 1)
        except Exception:
            next_exp_id += 1

    next_settle_id = 1
    for settlement in data["settlements"]:
        if "id" not in settlement:
            settlement["id"] = next_settle_id
        try:
            settlement["amount"] = float(settlement.get("amount", 0))
            next_settle_id = max(next_settle_id, int(settlement.get("id", 0)) + 1)
        except Exception:
            next_settle_id += 1

    return data


def google_sheets_ready():
    """True when Streamlit Secrets contain the Google service account and sheet URL."""
    try:
        return (
            gspread is not None
            and Credentials is not None
            and "spreadsheet_url" in st.secrets
            and "gcp_service_account" in st.secrets
        )
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    service_account_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_url(st.secrets["spreadsheet_url"])


def get_or_create_worksheet(sheet, name, headers):
    try:
        ws = sheet.worksheet(name)
    except Exception:
        ws = sheet.add_worksheet(title=name, rows=1000, cols=max(len(headers), 3))

    values = ws.get_all_values()
    if not values:
        ws.update("A1", [headers])
    elif values[0] != headers:
        ws.clear()
        ws.update("A1", [headers])
    return ws


def load_from_google_sheets():
    sheet = get_spreadsheet()
    worksheets = {
        name: get_or_create_worksheet(sheet, name, headers)
        for name, headers in SHEET_HEADERS.items()
    }

    data = default_data()

    group_rows = worksheets["groups"].get_all_records()
    if group_rows:
        groups = {}
        for row in group_rows:
            group_name = str(row.get("group_name", "")).strip()
            member_name = str(row.get("member_name", "")).strip()
            color = str(row.get("color", "#1DB954")).strip() or "#1DB954"
            if not group_name or not member_name:
                continue
            if group_name not in groups:
                groups[group_name] = {"name": group_name, "members": [], "color": color}
            if member_name not in groups[group_name]["members"]:
                groups[group_name]["members"].append(member_name)
        data["groups"] = list(groups.values()) if groups else default_data()["groups"]

    expenses = []
    for row in worksheets["expenses"].get_all_records():
        try:
            participants = row.get("participants", "[]")
            split_details = row.get("split_details", "{}")
            if isinstance(participants, str):
                participants = json.loads(participants) if participants else []
            if isinstance(split_details, str):
                split_details = json.loads(split_details) if split_details else {}
            expenses.append({
                "id": int(row.get("id", 0) or 0),
                "description": str(row.get("description", "")),
                "amount": float(row.get("amount", 0) or 0),
                "category": str(row.get("category", "📦 Other")),
                "date": str(row.get("date", "")),
                "paid_by": str(row.get("paid_by", "")),
                "group": str(row.get("group", "General")),
                "split_type": str(row.get("split_type", "equal")),
                "participants": participants,
                "split_details": split_details,
                "created_at": str(row.get("created_at", "")),
            })
        except Exception:
            continue
    data["expenses"] = expenses

    settlements = []
    for row in worksheets["settlements"].get_all_records():
        try:
            settlements.append({
                "id": int(row.get("id", 0) or 0),
                "from": str(row.get("from", "")),
                "to": str(row.get("to", "")),
                "amount": float(row.get("amount", 0) or 0),
                "date": str(row.get("date", "")),
                "group": str(row.get("group", "General")),
                "created_at": str(row.get("created_at", "")),
            })
        except Exception:
            continue
    data["settlements"] = settlements

    activities = []
    for row in worksheets["activity_log"].get_all_records():
        msg = str(row.get("message", "")).strip()
        tm = str(row.get("time", "")).strip()
        if msg and tm:
            activities.append({"message": msg, "time": tm})
    data["activity_log"] = activities

    data = normalize_data(data)

    # If the sheet is empty, seed it with the default General group.
    if not group_rows:
        save_to_google_sheets(data)

    return data


def save_to_google_sheets(data):
    data = normalize_data(data)
    sheet = get_spreadsheet()

    # groups tab: one row per group/member combination
    group_rows = []
    for group in data["groups"]:
        for member in group.get("members", []):
            group_rows.append([
                group.get("name", ""),
                member,
                group.get("color", "#1DB954"),
            ])

    # expenses tab
    expense_rows = []
    for exp in data["expenses"]:
        expense_rows.append([
            exp.get("id", ""),
            exp.get("description", ""),
            exp.get("amount", 0),
            exp.get("category", ""),
            exp.get("date", ""),
            exp.get("paid_by", ""),
            exp.get("group", ""),
            exp.get("split_type", "equal"),
            json.dumps(exp.get("participants", []), ensure_ascii=False),
            json.dumps(exp.get("split_details", {}), ensure_ascii=False),
            exp.get("created_at", ""),
        ])

    # settlements tab
    settlement_rows = []
    for s in data["settlements"]:
        settlement_rows.append([
            s.get("id", ""),
            s.get("from", ""),
            s.get("to", ""),
            s.get("amount", 0),
            s.get("date", ""),
            s.get("group", ""),
            s.get("created_at", ""),
        ])

    # activity tab
    activity_rows = [
        [a.get("message", ""), a.get("time", "")]
        for a in data["activity_log"]
    ]

    rows_by_tab = {
        "groups": group_rows,
        "expenses": expense_rows,
        "settlements": settlement_rows,
        "activity_log": activity_rows,
    }

    for tab_name, headers in SHEET_HEADERS.items():
        ws = get_or_create_worksheet(sheet, tab_name, headers)
        ws.clear()
        ws.update("A1", [headers])
        rows = rows_by_tab.get(tab_name, [])
        if rows:
            ws.append_rows(rows, value_input_option="USER_ENTERED")


def load_from_local_json():
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return normalize_data(json.load(f))
        except Exception:
            return default_data()
    data = default_data()
    save_to_local_json(data)
    return data


def save_to_local_json(data):
    data = normalize_data(data)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_data():
    if google_sheets_ready():
        try:
            return load_from_google_sheets()
        except Exception as e:
            st.error(f"Google Sheets connection failed: {e}")
            st.warning("The app is temporarily using local JSON storage until the Google Sheets issue is fixed.")
            return load_from_local_json()
    else:
        st.info("Google Sheets storage is not configured. The app is using local JSON storage.")
        return load_from_local_json()


def save_data(data):
    if google_sheets_ready():
        try:
            save_to_google_sheets(data)
            return
        except Exception as e:
            st.error(f"Google Sheets save failed: {e}")
            st.warning("Saving to local JSON instead.")
    save_to_local_json(data)


def next_id(records):
    ids = []
    for record in records:
        try:
            ids.append(int(record.get("id", 0)))
        except Exception:
            pass
    return (max(ids) + 1) if ids else 1


def add_activity(data, msg):
    data["activity_log"].insert(0, {
        "message": msg,
        "time": datetime.datetime.now().isoformat(),
    })
    if len(data["activity_log"]) > 50:
        data["activity_log"] = data["activity_log"][:50]


def get_all_members(data):
    """Get unique members across all groups."""
    members = set()
    for g in data["groups"]:
        members.update(g["members"])
    return sorted(members)


# ─── BALANCE ENGINE ──────────────────────────────────────────────────────────

def compute_balances(data, group_filter=None):
    """Compute net balances, optionally filtered by group."""
    balances = defaultdict(float)

    expenses = data["expenses"]
    if group_filter:
        expenses = [e for e in expenses if e.get("group") == group_filter]

    for exp in expenses:
        payer = exp["paid_by"]
        total = exp["amount"]
        split = exp.get("split_type", "equal")
        participants = exp["participants"]
        split_details = exp.get("split_details", {})

        if split == "equal":
            share = total / len(participants)
            for p in participants:
                if p != payer:
                    balances[payer] += share
                    balances[p] -= share
        elif split == "exact":
            for p in participants:
                amt = split_details.get(p, 0)
                if p != payer:
                    balances[payer] += amt
                    balances[p] -= amt
        elif split == "percentage":
            for p in participants:
                pct = split_details.get(p, 0)
                amt = total * pct / 100
                if p != payer:
                    balances[payer] += amt
                    balances[p] -= amt

    settlements = data["settlements"]
    if group_filter:
        settlements = [s for s in settlements if s.get("group") == group_filter]

    for s in settlements:
        balances[s["from"]] += s["amount"]
        balances[s["to"]] -= s["amount"]

    return dict(balances)


def simplify_debts(balances):
    creditors, debtors = [], []
    for person, balance in balances.items():
        if balance > 0.01:
            creditors.append([balance, person])
        elif balance < -0.01:
            debtors.append([-balance, person])

    creditors.sort(reverse=True)
    debtors.sort(reverse=True)

    transactions = []
    i, j = 0, 0
    while i < len(creditors) and j < len(debtors):
        amount = min(creditors[i][0], debtors[j][0])
        if amount > 0.01:
            transactions.append({"from": debtors[j][1], "to": creditors[i][1], "amount": round(amount, 2)})
        creditors[i][0] -= amount
        debtors[j][0] -= amount
        if creditors[i][0] < 0.01: i += 1
        if debtors[j][0] < 0.01: j += 1
    return transactions


# ─── AVATAR ───────────────────────────────────────────────────────────────────

def avatar_color(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    colors = ["#1DB954","#E74C3C","#3498DB","#9B59B6","#F39C12","#1ABC9C","#E67E22","#2ECC71"]
    return colors[h % len(colors)]

def avatar_html(name, size=36):
    c = avatar_color(name)
    initial = name[0].upper()
    return f'<span style="display:inline-flex;align-items:center;justify-content:center;width:{size}px;height:{size}px;border-radius:50%;background:{c};color:white;font-weight:700;font-size:{size*0.45}px;">{initial}</span>'


# ─── LOAD DATA ────────────────────────────────────────────────────────────────

if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = True

data = load_data()
save_data(data)  # also upgrades old saved files with missing IDs

# Ensure active_group is valid
if st.session_state.active_group is None or not any(
    g["name"] == st.session_state.active_group for g in data["groups"]
):
    st.session_state.active_group = data["groups"][0]["name"] if data["groups"] else None


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📁 Groups")
    st.caption("Tap a group to select it")

    for g in data["groups"]:
        is_active = g["name"] == st.session_state.active_group
        badge_cls = "group-badge-active" if is_active else "group-badge"
        marker = " ◀" if is_active else ""

        if st.button(
            f"{'🔴' if is_active else '🟢'} {g['name']} ({len(g['members'])} members){marker}",
            key=f"grp_select_{g['name']}",
            use_container_width=True,
        ):
            st.session_state.active_group = g["name"]
            st.rerun()

    # ── Create new group ──
    st.markdown("---")
    with st.expander("➕ Create New Group"):
        gk = st.session_state.group_form_key
        grp_name = st.text_input("Group Name", placeholder="e.g. Goa Trip", key=f"grp_name_{gk}")
        grp_first_members = st.text_input(
            "Members (comma separated)",
            placeholder="e.g. Ravi, Priya, Surya",
            key=f"grp_first_members_{gk}",
        )
        if st.button("✅ Create Group", key=f"create_grp_btn_{gk}", use_container_width=True):
            if grp_name and grp_name.strip():
                # Check duplicate group name
                if any(g["name"].lower() == grp_name.strip().lower() for g in data["groups"]):
                    st.warning("Group name already exists!")
                else:
                    members = [m.strip() for m in grp_first_members.split(",") if m.strip()] if grp_first_members else []
                    if not members:
                        members = ["You"]
                    data["groups"].append({
                        "name": grp_name.strip(),
                        "members": members,
                        "color": "#1DB954",
                    })
                    add_activity(data, f"📁 Group '{grp_name.strip()}' created with {len(members)} members")
                    save_data(data)
                    st.session_state.active_group = grp_name.strip()
                    st.session_state.group_form_key += 1
                    st.session_state.success_msg = f"✅ Group '{grp_name.strip()}' created!"
                    st.rerun()
            else:
                st.warning("Enter a group name.")

    # ── Active group members ──
    st.markdown("---")
    active_grp = next((g for g in data["groups"] if g["name"] == st.session_state.active_group), None)

    if active_grp:
        st.markdown(f"### 👥 {active_grp['name']}")

        for m in active_grp["members"]:
            mc1, mc2 = st.columns([3, 1])
            with mc1:
                st.markdown(f"{avatar_html(m, 24)} &nbsp;**{m}**", unsafe_allow_html=True)
            with mc2:
                if st.button("✖", key=f"remove_{active_grp['name']}_{m}", help=f"Remove {m}"):
                    active_grp["members"].remove(m)
                    add_activity(data, f"👤 {m} removed from {active_grp['name']}")
                    save_data(data)
                    st.session_state.success_msg = f"❌ {m} removed from {active_grp['name']}"
                    st.rerun()

        # Add member to this group
        mk = st.session_state.member_add_key
        new_m = st.text_input(
            "Add member",
            placeholder="Type name & press Add",
            key=f"add_to_grp_{active_grp['name']}_{mk}",
            label_visibility="collapsed",
        )
        if st.button("➕ Add to Group", key=f"add_mem_btn_{active_grp['name']}_{mk}", use_container_width=True):
            if new_m and new_m.strip():
                clean = new_m.strip()
                if clean in active_grp["members"]:
                    st.warning(f"{clean} is already in this group!")
                else:
                    active_grp["members"].append(clean)
                    add_activity(data, f"👤 {clean} added to {active_grp['name']}")
                    save_data(data)
                    st.session_state.member_add_key += 1
                    st.session_state.success_msg = f"✅ {clean} added to {active_grp['name']}!"
                    st.rerun()

        # Delete group (not General)
        if active_grp["name"] != "General":
            st.markdown("---")
            if st.button(f"🗑️ Delete Group '{active_grp['name']}'", use_container_width=True):
                deleted_group = active_grp["name"]
                data["groups"] = [g for g in data["groups"] if g["name"] != deleted_group]
                data["expenses"] = [e for e in data["expenses"] if e.get("group") != deleted_group]
                data["settlements"] = [s for s in data["settlements"] if s.get("group") != deleted_group]
                add_activity(data, f"🗑️ Group '{deleted_group}' deleted, including related expenses and settlements")
                save_data(data)
                st.session_state.active_group = data["groups"][0]["name"] if data["groups"] else None
                st.session_state.success_msg = f"🗑️ Group '{active_grp['name']}' deleted"
                st.rerun()

    st.markdown("---")
    st.markdown(
        '<div style="text-align:center;font-size:0.75rem;color:#aaa;margin-top:1rem;">'
        '💸 SplitMate v2.0<br>Made with ❤️ & Streamlit</div>',
        unsafe_allow_html=True,
    )


# ─── HEADER ───────────────────────────────────────────────────────────────────

if st.session_state.success_msg:
    st.markdown(f'<div class="success-toast">{st.session_state.success_msg}</div>', unsafe_allow_html=True)
    st.session_state.success_msg = None

st.markdown(
    '<div class="hero"><h1>💸 SplitMate</h1>'
    '<p>Split expenses effortlessly — smarter than Splitwise.</p></div>',
    unsafe_allow_html=True,
)

# Show active group indicator
if st.session_state.active_group:
    st.markdown(
        f'<span style="font-size:0.9rem;color:#888;">Active group:</span> '
        f'<span class="group-badge">{st.session_state.active_group}</span>',
        unsafe_allow_html=True,
    )

# ─── MAIN TABS ────────────────────────────────────────────────────────────────

tab_dash, tab_add, tab_expenses, tab_balances, tab_settle, tab_activity = st.tabs([
    "📊 Dashboard", "➕ Add Expense", "📋 Expenses", "⚖️ Balances", "🤝 Settle Up", "🕑 Activity"
])

# ─── TAB: DASHBOARD ──────────────────────────────────────────────────────────

with tab_dash:
    balances = compute_balances(data)
    total_expenses = sum(e["amount"] for e in data["expenses"])
    total_settled = sum(s["amount"] for s in data["settlements"])
    you_balance = balances.get("You", 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="stat-card"><div class="stat-label">Total Expenses</div>'
                     f'<div class="stat-value stat-blue">${total_expenses:,.2f}</div></div>', unsafe_allow_html=True)
    with c2:
        color_cls = "stat-green" if you_balance >= 0 else "stat-red"
        label = "You are owed" if you_balance >= 0 else "You owe"
        st.markdown(f'<div class="stat-card"><div class="stat-label">{label}</div>'
                     f'<div class="stat-value {color_cls}">${abs(you_balance):,.2f}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-card"><div class="stat-label">Settled</div>'
                     f'<div class="stat-value stat-purple">${total_settled:,.2f}</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-card"><div class="stat-label">Transactions</div>'
                     f'<div class="stat-value stat-green">{len(data["expenses"])}</div></div>', unsafe_allow_html=True)

    st.markdown("####")
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("##### 📈 Recent Expenses")
        recent = data["expenses"][-5:][::-1]
        if recent:
            for exp in recent:
                cat_icon = exp.get("category", "📦 Other").split(" ")[0]
                st.markdown(
                    f'<div class="expense-card">'
                    f'<div><div class="title">{cat_icon} {exp["description"]}</div>'
                    f'<div class="meta">Paid by {exp["paid_by"]} · {exp["date"]} · {exp.get("group","")}</div></div>'
                    f'<div class="amount">${exp["amount"]:,.2f}</div></div>', unsafe_allow_html=True)
        else:
            st.info("No expenses yet. Add one to get started!")

    with col_right:
        st.markdown("##### 💰 Quick Balances")
        if balances:
            for person, bal in sorted(balances.items(), key=lambda x: x[1], reverse=True):
                if abs(bal) > 0.01:
                    cls = "balance-pos" if bal > 0 else "balance-neg"
                    sign = "+" if bal > 0 else ""
                    st.markdown(
                        f'<div class="{cls}">{avatar_html(person, 24)} &nbsp; <b>{person}</b> '
                        f'<span style="float:right;font-weight:700;">{sign}${bal:,.2f}</span></div>',
                        unsafe_allow_html=True)
        else:
            st.info("All settled up! 🎉")

        st.markdown("##### 🔄 Suggested Settlements")
        txns = simplify_debts(balances)
        if txns:
            for t in txns[:4]:
                st.markdown(
                    f'<div class="settle-row">{avatar_html(t["from"], 24)} &nbsp;<b>{t["from"]}</b> '
                    f'<span class="settle-arrow">→</span> '
                    f'{avatar_html(t["to"], 24)} &nbsp;<b>{t["to"]}</b> '
                    f'<span style="margin-left:auto;font-weight:700;color:#1DB954;">${t["amount"]:,.2f}</span></div>',
                    unsafe_allow_html=True)
        else:
            st.success("Everyone is settled up! 🎉")


# ─── TAB: ADD EXPENSE ────────────────────────────────────────────────────────

with tab_add:
    st.markdown("##### ➕ New Expense")

    ek = st.session_state.expense_form_key

    with st.form(key=f"add_expense_form_{ek}", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            description = st.text_input("📝 Description", placeholder="e.g. Dinner at Mario's")
            amount = st.number_input("💵 Amount ($)", min_value=0.01, step=0.01, value=0.01, format="%.2f")
            category = st.selectbox("🏷️ Category", list(CATEGORIES.keys()))
            date = st.date_input("📅 Date", value=datetime.date.today())

        with col2:
            group_names = [g["name"] for g in data["groups"]]
            default_idx = group_names.index(st.session_state.active_group) if st.session_state.active_group in group_names else 0
            selected_group = st.selectbox("📁 Group", group_names, index=default_idx)
            group_obj = next(g for g in data["groups"] if g["name"] == selected_group)

            if not group_obj["members"]:
                st.warning("This group has no members! Add members in the sidebar first.")

            paid_by = st.selectbox("💳 Paid by", group_obj["members"]) if group_obj["members"] else None
            split_type = st.radio("✂️ Split Type", ["equal", "exact", "percentage"], horizontal=True)
            participants = st.multiselect("👥 Split among", group_obj["members"], default=group_obj["members"])

        split_details = {}
        if split_type == "exact" and participants:
            st.markdown("##### 💲 Enter exact amounts:")
            cols = st.columns(min(len(participants), 4))
            for i, p in enumerate(participants):
                with cols[i % len(cols)]:
                    split_details[p] = st.number_input(f"{p}", min_value=0.0, step=0.01, format="%.2f", key=f"exact_{p}_{ek}")

        elif split_type == "percentage" and participants:
            st.markdown("##### 📊 Enter percentages:")
            cols = st.columns(min(len(participants), 4))
            for i, p in enumerate(participants):
                with cols[i % len(cols)]:
                    split_details[p] = st.number_input(
                        f"{p} (%)", min_value=0.0, max_value=100.0, step=1.0,
                        value=round(100.0 / len(participants), 1), key=f"pct_{p}_{ek}")

        st.markdown("")
        submitted = st.form_submit_button("✅ Add Expense", type="primary", use_container_width=True)

        if submitted:
            if description and description.strip() and amount > 0 and participants and paid_by:
                valid = True
                if split_type == "exact":
                    total_entered = sum(split_details.values())
                    if abs(total_entered - amount) > 0.01 and total_entered > 0:
                        st.warning(f"⚠️ Amounts total ${total_entered:.2f}, but expense is ${amount:.2f}")
                        valid = False
                elif split_type == "percentage":
                    total_pct = sum(split_details.values())
                    if abs(total_pct - 100) > 0.1:
                        st.warning(f"⚠️ Percentages total {total_pct:.1f}%, should be 100%")
                        valid = False
                if valid:
                    expense = {
                        "id": next_id(data["expenses"]),
                        "description": description.strip(),
                        "amount": amount, "category": category,
                        "date": str(date), "paid_by": paid_by,
                        "group": selected_group, "split_type": split_type,
                        "participants": participants, "split_details": split_details,
                        "created_at": datetime.datetime.now().isoformat(),
                    }
                    data["expenses"].append(expense)
                    add_activity(data, f"💸 {paid_by} added '{description.strip()}' — ${amount:.2f} ({selected_group})")
                    save_data(data)
                    st.session_state.expense_form_key += 1
                    st.session_state.success_msg = f"✅ Expense '{description.strip()}' (${amount:.2f}) added to {selected_group}!"
                    st.rerun()
            else:
                st.error("Fill in all fields and ensure the group has members.")


# ─── TAB: EXPENSES ───────────────────────────────────────────────────────────

with tab_expenses:
    st.markdown("##### 📋 All Expenses")

    fc1, fc2 = st.columns(2)
    with fc1:
        filter_group = st.selectbox("Filter by Group", ["All"] + [g["name"] for g in data["groups"]], key="filter_grp")
    with fc2:
        filter_cat = st.selectbox("Filter by Category", ["All"] + list(CATEGORIES.keys()), key="filter_cat")

    filtered = data["expenses"][::-1]
    if filter_group != "All":
        filtered = [e for e in filtered if e.get("group") == filter_group]
    if filter_cat != "All":
        filtered = [e for e in filtered if e.get("category") == filter_cat]

    if filtered:
        for exp in filtered:
            cat_icon = exp.get("category", "📦 Other").split(" ")[0]
            ec1, ec2 = st.columns([5, 1])
            with ec1:
                st.markdown(
                    f'<div class="expense-card">'
                    f'<div><div class="title">{cat_icon} {exp["description"]}</div>'
                    f'<div class="meta">Paid by {exp["paid_by"]} · {exp["date"]} · '
                    f'{exp.get("group", "General")} · Split: {exp.get("split_type", "equal")}</div>'
                    f'<div class="meta">Among: {", ".join(exp["participants"])}</div></div>'
                    f'<div class="amount">${exp["amount"]:,.2f}</div></div>', unsafe_allow_html=True)
            with ec2:
                st.write("")
                st.write("")
                if st.button("🗑️ Delete", key=f"delete_expense_{exp.get('id')}", use_container_width=True):
                    data["expenses"] = [e for e in data["expenses"] if e.get("id") != exp.get("id")]
                    add_activity(data, f"🗑️ Expense '{exp['description']}' deleted")
                    save_data(data)
                    st.session_state.success_msg = f"🗑️ Expense '{exp['description']}' deleted."
                    st.rerun()

        st.markdown("---")
        st.markdown(f"**Total: ${sum(e['amount'] for e in filtered):,.2f}** across **{len(filtered)}** expenses")
    else:
        st.info("No expenses found.")


# ─── TAB: BALANCES ───────────────────────────────────────────────────────────

with tab_balances:
    st.markdown("##### ⚖️ Net Balances")

    bal_group = st.selectbox("View balances for", ["All Groups"] + [g["name"] for g in data["groups"]], key="bal_grp_filter")
    grp_f = None if bal_group == "All Groups" else bal_group
    balances = compute_balances(data, group_filter=grp_f)

    if balances and any(abs(b) > 0.01 for b in balances.values()):
        total_owed = sum(b for b in balances.values() if b > 0)
        st.markdown(f"**Total outstanding:** ${total_owed:,.2f}")
        st.markdown("####")

        max_abs = max(abs(b) for b in balances.values()) if balances else 1

        for person in sorted(balances, key=lambda x: balances[x], reverse=True):
            bal = balances[person]
            if abs(bal) < 0.01:
                continue
            col_a, col_b, col_c = st.columns([1, 3, 1])
            with col_a:
                st.markdown(f"{avatar_html(person, 32)} **{person}**", unsafe_allow_html=True)
            with col_b:
                pct = abs(bal) / max_abs * 100
                color = "#1DB954" if bal > 0 else "#E74C3C"
                direction = "right" if bal > 0 else "left"
                st.markdown(
                    f'<div style="background:#f0f0f0;border-radius:8px;height:28px;overflow:hidden;">'
                    f'<div style="background:{color};height:100%;width:{pct}%;border-radius:8px;'
                    f'float:{direction};"></div></div>', unsafe_allow_html=True)
            with col_c:
                sign = "+" if bal > 0 else ""
                color = "#1DB954" if bal > 0 else "#E74C3C"
                st.markdown(f'<span style="font-weight:700;font-size:1.1rem;color:{color};">{sign}${bal:,.2f}</span>',
                             unsafe_allow_html=True)
    else:
        st.info("No balances to show. Add some expenses first!")


# ─── TAB: SETTLE UP ──────────────────────────────────────────────────────────

with tab_settle:
    st.markdown("##### 🤝 Settle Up")

    settle_group = st.selectbox("Settle for", ["All Groups"] + [g["name"] for g in data["groups"]], key="settle_grp_filter")
    grp_f = None if settle_group == "All Groups" else settle_group
    balances = compute_balances(data, group_filter=grp_f)
    txns = simplify_debts(balances)

    if txns:
        st.markdown("**Optimal settlement plan** (fewest transactions):")
        st.markdown("")

        for i, t in enumerate(txns):
            sc1, sc2 = st.columns([4, 1])
            with sc1:
                st.markdown(
                    f'<div class="settle-row">{avatar_html(t["from"], 30)} &nbsp;<b>{t["from"]}</b> '
                    f'<span class="settle-arrow">➜</span> '
                    f'{avatar_html(t["to"], 30)} &nbsp;<b>{t["to"]}</b> '
                    f'<span style="margin-left:auto;font-weight:800;font-size:1.1rem;color:#1DB954;">'
                    f'${t["amount"]:,.2f}</span></div>', unsafe_allow_html=True)
            with sc2:
                if st.button("✅ Settle", key=f"settle_{i}", use_container_width=True):
                    data["settlements"].append({
                        "id": next_id(data["settlements"]),
                        "from": t["from"], "to": t["to"],
                        "amount": t["amount"], "date": str(datetime.date.today()),
                        "group": settle_group if settle_group != "All Groups" else "General",
                    })
                    add_activity(data, f"🤝 {t['from']} paid {t['to']} ${t['amount']:.2f}")
                    save_data(data)
                    st.session_state.success_msg = f"✅ Settled! {t['from']} → {t['to']}: ${t['amount']:.2f}"
                    st.rerun()

        st.markdown("---")
        st.markdown("##### 📝 Record Custom Settlement")

        sk = st.session_state.settle_form_key
        all_members = get_all_members(data)
        with st.form(key=f"custom_settle_form_{sk}", clear_on_submit=True):
            cs1, cs2, cs3 = st.columns(3)
            with cs1:
                settle_from = st.selectbox("From", all_members)
            with cs2:
                settle_to = st.selectbox("To", all_members)
            with cs3:
                settle_amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)

            submitted = st.form_submit_button("💰 Record Settlement", type="primary")
            if submitted:
                if settle_from != settle_to and settle_amount > 0:
                    data["settlements"].append({
                        "id": next_id(data["settlements"]),
                        "from": settle_from, "to": settle_to,
                        "amount": settle_amount, "date": str(datetime.date.today()),
                        "group": settle_group if settle_group != "All Groups" else "General",
                    })
                    add_activity(data, f"🤝 {settle_from} paid {settle_to} ${settle_amount:.2f}")
                    save_data(data)
                    st.session_state.settle_form_key += 1
                    st.session_state.success_msg = f"✅ Settlement: {settle_from} → {settle_to}: ${settle_amount:.2f}"
                    st.rerun()
                else:
                    st.warning("'From' and 'To' must be different.")
    else:
        st.success("🎉 Everyone is settled up!")

    if data["settlements"]:
        st.markdown("---")
        st.markdown("##### 📜 Settlement History")
        for s in data["settlements"][::-1]:
            hc1, hc2 = st.columns([5, 1])
            with hc1:
                st.markdown(
                    f'<div class="settle-row">{avatar_html(s["from"], 24)} <b>{s["from"]}</b> '
                    f'<span class="settle-arrow">→</span> '
                    f'{avatar_html(s["to"], 24)} <b>{s["to"]}</b> '
                    f'<span style="margin-left:auto;font-weight:700;">${s["amount"]:,.2f}</span> '
                    f'<span style="color:#aaa;font-size:0.8rem;margin-left:0.5rem;">{s["date"]}</span></div>',
                    unsafe_allow_html=True)
            with hc2:
                if st.button("🗑️ Delete", key=f"delete_settlement_{s.get('id')}", use_container_width=True):
                    data["settlements"] = [x for x in data["settlements"] if x.get("id") != s.get("id")]
                    add_activity(data, f"🗑️ Settlement {s['from']} → {s['to']} ${s['amount']:.2f} deleted")
                    save_data(data)
                    st.session_state.success_msg = "🗑️ Settlement deleted."
                    st.rerun()


# ─── TAB: ACTIVITY ───────────────────────────────────────────────────────────

with tab_activity:
    st.markdown("##### 🕑 Activity Feed")

    if data["activity_log"]:
        for item in data["activity_log"]:
            ts = datetime.datetime.fromisoformat(item["time"])
            time_str = ts.strftime("%b %d, %I:%M %p")
            st.markdown(
                f'<div class="activity-item">{item["message"]} '
                f'<span class="activity-time">{time_str}</span></div>', unsafe_allow_html=True)
    else:
        st.info("No activity yet.")

    if data["activity_log"]:
        st.markdown("---")
        if st.button("🗑️ Clear Activity Log"):
            data["activity_log"] = []
            save_data(data)
            st.rerun()


# ─── FOOTER DATA MANAGEMENT ──────────────────────────────────────────────────

st.markdown("---")

with st.expander("⚙️ Data Management"):
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        if st.button("📥 Export Data (JSON)", use_container_width=True):
            st.download_button("⬇️ Download", json.dumps(data, indent=2, default=str),
                               "splitmate_backup.json", "application/json")
    with dc2:
        uploaded = st.file_uploader("📤 Import Data", type=["json"], key="import_file")
        if uploaded:
            imported = normalize_data(json.load(uploaded))
            data.clear()
            data.update(imported)
            save_data(data)
            st.success("Data imported!")
            st.rerun()
    with dc3:
        if st.button("🗑️ Reset All Data", type="secondary", use_container_width=True):
            st.session_state.show_reset_confirm = True

    if st.session_state.show_reset_confirm:
        st.markdown("")
        st.warning("⚠️ This will permanently delete ALL data. Enter admin password.")
        with st.form(key="reset_confirm_form", clear_on_submit=True):
            reset_pw = st.text_input("🔒 Admin Password", type="password", placeholder="Enter password")
            rc1, rc2 = st.columns(2)
            with rc1:
                confirm_btn = st.form_submit_button("🗑️ Yes, Reset", type="primary", use_container_width=True)
            with rc2:
                cancel_btn = st.form_submit_button("❌ Cancel", use_container_width=True)

            if confirm_btn:
                if reset_pw == ADMIN_PASSWORD:
                    save_data(default_data())
                    st.session_state.show_reset_confirm = False
                    st.session_state.success_msg = "🗑️ All data has been reset."
                    st.rerun()
                else:
                    st.error("❌ Wrong password!")
            if cancel_btn:
                st.session_state.show_reset_confirm = False
                st.rerun()
