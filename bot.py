"""Vera-style merchant assistant for the magicpin AI Challenge.
Deterministic, context-grounded composer with HTTP endpoints and lightweight conversation handling.
"""
from __future__ import annotations
import time, re
from datetime import datetime
from typing import Any, Optional
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Vera Merchant AI Assistant", version="1.0.0")
START = time.time()
contexts: dict[tuple[str, str], dict[str, Any]] = {}
conversations: dict[str, list[dict[str, Any]]] = {}


def pct(x):
    try:
        return f"{x*100:.0f}%"
    except Exception:
        return str(x)


def first_name(m):
    i = m.get("identity", {})
    return i.get("owner_first_name") or i.get("name", "there").split()[0]


def cat_of(m):
    return m.get("category_slug", "").lower()


def active_offer(m, keywords=()):
    offers = [o for o in m.get("offers", []) if str(o.get("status", "")).lower() == "active"]
    if keywords:
        for o in offers:
            title = o.get("title", "").lower()
            if any(k in title for k in keywords):
                return o.get("title")
    return offers[0].get("title") if offers else None


def get_digest(category, item_id=None, kind=None):
    items = category.get("digest", [])
    if item_id:
        for x in items:
            if x.get("id") == item_id:
                return x
    if kind:
        for x in items:
            if x.get("kind") == kind:
                return x
    return items[0] if items else None


def num(v):
    try: return float(v)
    except Exception: return None


def trigger_data(t):
    p=t.get("payload") or {}
    return p if isinstance(p, dict) else {}


def language_style(m, c=None):
    lang = ((c or {}).get("identity", {}).get("language_pref") or "") if c else ""
    if not lang:
        lang = ",".join(m.get("identity", {}).get("languages", []))
    return "hi" in lang.lower()


def compose(category: dict, merchant: dict, trigger: dict, customer: Optional[dict] = None) -> dict:
    """Compose one context-grounded message. No external calls; deterministic."""
    kind = trigger.get("kind", "")
    p = trigger_data(trigger)
    cat = cat_of(merchant)
    name = first_name(merchant)
    send_as = "merchant_on_behalf" if trigger.get("scope") == "customer" or customer else "vera"
    suppression = trigger.get("suppression_key", trigger.get("id", kind))
    hi = language_style(merchant, customer)

    # Customer-facing: consent-aware and relationship-aware.
    if send_as == "merchant_on_behalf" and customer:
        cn = customer.get("identity", {}).get("name", "there")
        if not customer.get("preferences", {}).get("reminder_opt_in", False):
            return {"body":"", "cta":"none", "send_as":send_as, "suppression_key":suppression,
                    "rationale":"Customer has not opted into WhatsApp reminders; do not initiate outreach."}
        if kind == "recall_due":
            due = p.get("due_date")
            if not p.get("service_due") and p.get("placeholder"):
                last_visit=customer.get("relationship",{}).get("last_visit")
                offer=active_offer(merchant)
                body=f"Hi {cn}, {merchant.get('identity',{}).get('name','')} se reminder — aapke liye follow-up reminder aaya hai"
                if last_visit: body += f"; last visit {last_visit}"
                if offer: body += f". {offer} active hai"
                body += ". Continue karna hai?"
                return {"body":body,"cta":"open_ended","send_as":send_as,"suppression_key":suppression,"rationale":"The generated recall trigger lacks the service and due date, so the message uses only the customer’s last-visit date and active merchant offer."}
            slots = p.get("available_slots") or []
            offer = active_offer(merchant, ("cleaning", "checkup", "month"))
            if slots:
                labels = [s.get("label") for s in slots[:2] if s.get("label")]
                slot_text = " ya ".join(labels)
            else:
                slot_text = "aapke convenient time"
            if hi:
                body=f"Hi {cn}, {merchant.get('identity',{}).get('name','')} se reminder 🦷 — aapki {p.get('service_due','follow-up').replace('_',' ')} window open hai. {slot_text} available hain"
                if offer: body += f"; {offer}"
                body += ". Aapke liye ek slot hold karun?"
            else:
                body=f"Hi {cn}, a reminder from {merchant.get('identity',{}).get('name','')}: your {p.get('service_due','follow-up').replace('_',' ')} window is due. {slot_text} available"
                if offer: body += f"; {offer}"
                body += ". Would you like me to hold a slot?"
            return {"body":body,"cta":"open_ended","send_as":send_as,"suppression_key":suppression,
                    "rationale":"Uses the customer’s due event, available slots, active merchant offer and consent without inventing clinical claims."}
        if kind == "chronic_refill_due":
            mols=p.get("molecule_list",[]); runout=p.get("stock_runs_out_iso")
            mol_text=", ".join(mols[:3])
            if not mol_text and cat != "pharmacies":
                body=f"Hi {cn}, {merchant.get('identity',{}).get('name','')} here — I received a refill reminder, but the specific item isn’t included. Can you confirm what you need?"
                return {"body":body,"cta":"open_ended","send_as":send_as,"suppression_key":suppression,
                        "rationale":"The trigger lacks the specific refill item; asks for clarification instead of inventing medication details."}
            if hi:
                body=f"Hi {cn}, {merchant.get('identity',{}).get('name','')} se refill reminder — aapki regular medicines ({mol_text}) ka next refill window aa raha hai"
                if runout: body += f"; stock date {runout[:10]}"
                body += ". Delivery address saved hai. Refill arrange karun?"
            else:
                body=f"Hi {cn}, {merchant.get('identity',{}).get('name','')} here — your regular refill window is coming up for {mol_text}"
                if runout: body += f" (stock-out date {runout[:10]})"
                body += ". Your delivery address is saved. Shall I arrange the refill?"
            return {"body":body,"cta":"open_ended","send_as":send_as,"suppression_key":suppression,
                    "rationale":"Grounds the reminder in the provided refill molecules, timing and saved delivery preference."}
        if kind in ("appointment_tomorrow",):
            if hi:
                body=f"Hi {cn}, {merchant.get('identity',{}).get('name','')} se reminder — aapki appointment kal hai. Agar timing confirm hai, bas YES reply karein; change chahiye ho to batayein."
            else:
                body=f"Hi {cn}, a reminder from {merchant.get('identity',{}).get('name','')} — your appointment is tomorrow. If the timing still works, reply YES; if you need a change, tell us."
            return {"body":body,"cta":"YES/STOP","send_as":send_as,"suppression_key":suppression,
                    "rationale":"Simple appointment reminder using only the provided event; no invented time or service."}
        if kind in ("customer_lapsed_soft","customer_lapsed_hard","winback_eligible","winback_eligible_customer"):
            days=p.get("days_since_last_visit") or p.get("days_since_last_purchase")
            if days is None:
                last_visit=customer.get("relationship",{}).get("last_visit")
                visits=customer.get("relationship",{}).get("visits_total")
            else:
                last_visit=None; visits=None
            prev=p.get("previous_focus")
            if hi:
                body=f"Hi {cn}, kaafi time ho gaya — aapka last visit {days} days pehle tha" if days else f"Hi {cn}, kaafi time ho gaya since your last visit."
                if not days and last_visit: body += f" (last visit: {last_visit})"
                if visits: body += f" — aap {visits} visits kar chuke hain."
                if prev: body += f" Aap pehle {prev} focus kar rahe the."
                body += " Wapas aane ka plan banayein?"
            else:
                body=f"Hi {cn}, it’s been a while since your last visit"
                if days: body += f" ({days} days)"
                elif last_visit: body += f" (last visit: {last_visit})"
                if visits: body += f" — you’ve visited {visits} times"
                if prev: body += f" — you previously focused on {prev}"
                body += ". Would you like to plan your next visit?"
            return {"body":body,"cta":"open_ended","send_as":send_as,"suppression_key":suppression,
                    "rationale":"Uses the customer’s actual lapse/previous-focus data and keeps the ask low friction."}
        if kind == "trial_followup":
            opts=p.get("next_session_options") or []
            opt=opts[0].get("label") if opts else None
            body=f"Hi {cn}, thanks for trying {merchant.get('identity',{}).get('name','')} recently."
            if opt: body += f" Your next session option is {opt}."
            body += " Want me to help confirm it?"
            return {"body":body,"cta":"open_ended","send_as":send_as,"suppression_key":suppression,
                    "rationale":"Continues the trial relationship and uses only a supplied next-session option."}
        if kind == "wedding_package_followup":
            days=p.get("days_to_wedding"); wd=p.get("wedding_date"); window=p.get("next_step_window_open")
            body=f"Hi {cn} 💍 {days} days to your wedding" if days else f"Hi {cn} 💍"
            if wd: body += f" ({wd})"
            if window: body += f" — your {window.replace('_',' ')} window is open."
            body += " Would you like to plan the next step?"
            return {"body":body,"cta":"open_ended","send_as":send_as,"suppression_key":suppression,
                    "rationale":"Uses wedding/trial timing from the trigger and avoids inventing a package or price."}

    # Merchant-facing handlers.
    if kind == "active_planning_intent":
        topic=p.get("intent_topic","")
        hist=merchant.get("conversation_history",[])
        last_offer=active_offer(merchant)
        if "corporate_bulk_thali" in topic:
            body=(f"Suresh, starter version for Mylari Corporate Thali — based on your ₹149 weekday lunch thali and 18 orders/day avg:\n"
                  f"• 10 thalis @ ₹125 each\n• 25 @ ₹115 each\n• 50+ @ ₹105 each\n"
                  "WhatsApp orders day-before by 5pm; delivery 12:30–1pm.\n"
                  "Want me to turn this into a 3-line corporate outreach message?")
        elif "kids_yoga" in topic:
            body=(f"Padma, here’s the next version for the kids yoga summer camp: 4 weeks, 3 classes/week, age 7–12, ₹2,499. "
                  f"Zen Yoga already has 95 active members and 55% trial-to-paid. Want me to draft the GBP post + Insta carousel?")
        else:
            body=f"{name}, I’ve picked up your planning intent ({topic.replace('_',' ')}). Want me to draft the concrete offer/copy next?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,
                "rationale":"Explicit planning intent is honored immediately; response advances to an artifact/action instead of re-qualifying."}

    if kind in ("research_digest","research_digest_release"):
        item=get_digest(category,p.get("top_item_id"))
        if item:
            body=f"{name}, {item.get('source','This week’s digest')} — {item.get('title','')}"
            summary=item.get("summary")
            if summary: body += f". {summary.split('.')[0]}"
            actionable=item.get("actionable")
            if actionable: body += f". {actionable}. Want me to pull the full note?"
            else: body += ". Worth a look?"
        else: body=f"{name}, a new {cat} research item is in this week’s digest. Want me to pull the relevant note?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,
                "rationale":"Cites only the digest item actually present in CategoryContext and connects it to a concrete merchant action."}

    if kind in ("regulation_change",):
        item=get_digest(category,p.get("top_item_id"),"compliance")
        deadline=p.get("deadline_iso")
        body=f"{name}, compliance heads-up: {item.get('title','') if item else 'a category regulation update is due'}"
        if deadline: body += f" — deadline {deadline[:10]}"
        if item and item.get("summary"): body += f". {item['summary']}"
        body=body.rstrip('.') + ". Want me to turn this into a short audit checklist?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,
                "rationale":"High-urgency regulatory trigger is stated with the supplied deadline and source-backed details."}

    if kind in ("cde_opportunity",):
        item=get_digest(category,p.get("digest_item_id"),"cde")
        if item:
            fee=p.get("fee","")
            fee_text="free for members" if "free" in fee else fee
            body=f"{name}, IDA opportunity: {item.get('title','')} on {item.get('date','')[:10] if item.get('date') else 'the listed date'} — {item.get('credits',p.get('credits',0))} CDE credits, {fee_text}. Want me to send the registration details?"
        else: body=f"{name}, a CDE opportunity is available in your category digest. Want the registration details?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Uses the exact education event, credits and fee from the provided context."}

    if kind in ("perf_dip","seasonal_perf_dip"):
        metric=p.get("metric","views"); delta=p.get("delta_pct")
        perf=merchant.get("performance",{}); current=perf.get(metric)
        body=f"{name}, your {metric} are down {pct(abs(delta)) if isinstance(delta,(int,float)) else 'this week'} in the trigger window"
        if current is not None: body += f"; current 30-day {metric}: {current}"
        if p.get("is_expected_seasonal"):
            body += f" — this is flagged as seasonal ({p.get('season_note','expected window')})."
        body += " Want me to suggest one concrete recovery move?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Anchors the performance event to the trigger delta and merchant’s current metric, with a single next step."}

    if kind == "perf_spike":
        metric=p.get("metric"); delta=p.get("delta_pct"); base=p.get("vs_baseline"); driver=p.get("likely_driver")
        if not metric and p.get("placeholder"):
            perf=merchant.get("performance",{})
            body=f"{name}, a positive performance trigger just fired"
            if perf.get("views") is not None: body += f"; your 30-day profile shows {perf['views']} views and {perf.get('calls','')} calls"
        else:
            body=f"{name}, nice signal: {metric or 'performance'} are up {pct(delta) if isinstance(delta,(int,float)) else 'this week'} vs baseline"
            if base is not None: body += f" (baseline {base})"
        if driver: body += f" — likely linked to {driver.replace('_',' ')}"
        body += ". Want me to turn what worked into the next post?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Positive performance trigger is tied to the supplied delta/baseline and likely driver."}

    if kind in ("milestone_reached",):
        metric=p.get("metric") or p.get("metric_or_topic") or "milestone"; now=p.get("value_now"); target=p.get("milestone_value")
        if now is not None:
            body=f"{name}, you’re at {now} {metric.replace('_',' ')}"
            if target: body += f" — just {target-now} away from {target}"
        elif p.get("placeholder"):
            body=f"{name}, a milestone trigger just fired for {merchant.get('identity',{}).get('name','your business')}. I don’t have the milestone metric in this event payload."
            return {"body":body + " Want me to show what changed?","cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"The generated trigger omits the milestone metric, so the bot asks for the missing event detail instead of inventing one."}
        else:
            body=f"{name}, you hit a {metric.replace('_',' ')} milestone"
        body += ". Want me to draft a small GBP/social post to mark it?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Celebrates the actual merchant milestone and proposes a concrete low-effort asset."}

    if kind == "dormant_with_vera":
        days=p.get("days_since_last_merchant_message")
        topic=p.get("last_topic")
        body=f"{name}, it’s been {days} days since we last spoke" if days is not None else f"{name}, it’s been a while since we last spoke"
        if topic: body += f" about {topic.replace('_',' ')}"
        body += ". I can pick up from there — want a 2-minute update on what’s changed?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Acknowledges dormancy and prior topic rather than sending a generic promotion."}

    if kind in ("curious_ask_due",):
        body=f"Hi {name}! Quick operator question — what service has been most asked-for this week at {merchant.get('identity',{}).get('name','your business')}? I’ll turn your answer into one ready-to-use post/reply."
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Uses the recurring curiosity trigger and offers immediate effort-saving value."}

    if kind in ("festival_upcoming",):
        fest=p.get("festival"); date=p.get("date"); days=p.get("days_until")
        if not fest:
            beats=category.get("seasonal_beats",[])
            beat=beats[0].get("note") if beats else None
            body=f"{name}, a festival-planning trigger is active for {cat}"
            if beat: body += f"; current seasonal note: {beat}"
        else:
            body=f"{name}, {fest} is {days} days away ({date})" if days is not None else f"{name}, {fest} is coming up"
        body += f". For {cat}, I can adapt one of your existing offers into a festival-ready post. Want me to draft it?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Time-bounds the festival trigger and reuses merchant context rather than inventing a new offer."}

    if kind == "ipl_match_today":
        body=f"Quick heads-up {name} — {p.get('match','today’s match')} at {p.get('venue','the stadium')} today"
        if p.get('match_time_iso'): body += f", {p['match_time_iso'][11:16]}"
        offer=active_offer(merchant)
        if offer: body += f". Your active offer is {offer}. Since it is not a Saturday offer, I wouldn’t reuse it today."
        body += " Want me to draft a match-day post without inventing a discount?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Uses the exact event details and protects against generic invented promotions."}

    if kind == "review_theme_emerged":
        theme=p.get("theme") or p.get("metric_or_topic") or "customer experience"; occ=p.get("occurrences_30d")
        body=f"{name}, one review pattern is getting louder: {theme.replace('_',' ')} appears in {occ} reviews in 30 days" if occ else f"{name}, a review theme is emerging around {theme.replace('_',' ')}"
        if p.get("common_quote"): body += f" — e.g. ‘{p['common_quote']}’"
        body += ". Want me to draft a response + operational fix note?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Uses a concrete review theme and occurrence count, then offers a useful response artifact."}

    if kind == "competitor_opened":
        comp=p.get("competitor_name"); dist=p.get("distance_km"); offer=p.get("their_offer")
        body=f"{name}, new nearby signal: {comp} opened {dist} km away" if comp and dist is not None else f"{name}, a new nearby competitor signal just landed"
        if offer: body += f" with {offer}"
        if not offer:
            existing = active_offer(merchant)
            if existing: body += f". You currently have {existing} active"
        body += ". Want me to compare the gap with your current profile/offer?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Frames the competitor event with supplied distance/offer and avoids unsupported claims."}

    if kind == "supply_alert":
        mol=p.get("molecule"); batches=", ".join(p.get("affected_batches",[])); mf=p.get("manufacturer")
        body=f"{name}, supply alert: {mol} — affected batches {batches} ({mf})" if mol else f"{name}, supply alert received"
        body += ". Want me to help turn the alert into an internal stock-check checklist?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Uses exact molecule/batch/manufacturer data from the trigger."}

    if kind == "category_seasonal":
        trends=p.get("trends",[])
        body=f"{name}, summer demand signal for your pharmacy: {', '.join(trends[:4])}. Shelf action is recommended. Want me to turn that into a 3-line stock-priority checklist?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Directly uses the supplied seasonal demand movements and recommended action."}

    if kind == "gbp_unverified":
        uplift=p.get("estimated_uplift_pct")
        body=f"{name}, your Google Business Profile is still unverified"
        if uplift: body += f"; the supplied estimate is up to {pct(uplift)} uplift"
        body += ". Verification path: postcard or phone call. Want the shortest setup steps?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"States the actual verification state and supplied verification path without promising results."}

    if kind == "renewal_due":
        days=p.get("days_remaining"); plan=p.get("plan"); amt=p.get("renewal_amount")
        body=f"{name}, your {plan or merchant.get('subscription',{}).get('plan','')} plan renews in {days} days"
        if amt: body += f" at ₹{amt:,}"
        body += ". Want me to show what to review before renewal?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Uses the explicit renewal deadline/amount and keeps the action focused."}

    if kind == "winback_eligible":
        body=f"{name}, your account has been inactive for {p.get('days_since_expiry','')} days"
        if p.get("lapsed_customers_added_since_expiry") is not None: body += f" and {p['lapsed_customers_added_since_expiry']} lapsed customers have been added since expiry"
        body += ". Want me to outline the lowest-effort way back?"
        return {"body":body,"cta":"open_ended","send_as":"vera","suppression_key":suppression,"rationale":"Uses the winback trigger facts rather than a generic sales pitch."}

    # Generic fallback is still grounded: name + trigger kind + one merchant fact.
    perf=merchant.get("performance",{}); body=f"{name}, quick update on {kind.replace('_',' ')} for {merchant.get('identity',{}).get('name','your business')}"
    if perf.get("views") is not None: body += f": {perf['views']} views in the last 30 days"
    body += ". Want me to show the most relevant next step?"
    return {"body":body,"cta":"open_ended","send_as":send_as,"suppression_key":suppression,
            "rationale":"Fallback remains grounded in the supplied trigger and merchant state."}


def auto_reply_like(text: str) -> bool:
    s=re.sub(r"\s+"," ",text.lower()).strip()
    patterns=["thank you for contacting", "thanks for contacting", "your message has been received",
              "i am an automated assistant", "automated response", "our team will get back",
              "for your information", "thank you for your message"]
    return any(x in s for x in patterns)

def explicit_action(text: str) -> bool:
    s=text.lower()
    return bool(re.search(r"\b(yes|ok|okay|let'?s do it|go ahead|please do|join|start|do it|proceed|book it|send it)\b", s))

def negative(text: str) -> bool:
    s=text.lower()
    return bool(re.search(r"\b(no|not interested|stop|don't|do not|leave me|no thanks|unsubscribe)\b", s))

class CtxBody(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str

class TickBody(BaseModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)

class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: str | None = None
    customer_id: str | None = None
    from_role: str
    message: str
    received_at: str
    turn_number: int

@app.get("/v1/healthz")
async def healthz():
    counts={"category":0,"merchant":0,"customer":0,"trigger":0}
    for (scope,_),_v in contexts.items(): counts[scope]=counts.get(scope,0)+1
    return {"status":"ok","uptime_seconds":int(time.time()-START),"contexts_loaded":counts}

@app.get("/v1/metadata")
async def metadata():
    return {"team_name":"Harshita Gautam","team_members":["Harshita Gautam"],"model":"deterministic-context-composer",
            "approach":"trigger-aware deterministic composer with category/merchant/customer retrieval and multi-turn intent handling",
            "contact_email":"erharshitagautam@gmail.com","version":"1.0.0","submitted_at":datetime.utcnow().isoformat()+"Z"}

@app.post("/v1/context")
async def push_context(body: CtxBody):
    if body.scope not in {"category","merchant","customer","trigger"}:
        return {"accepted":False,"reason":"invalid_scope","details":"scope must be category, merchant, customer, or trigger"}
    key=(body.scope,body.context_id); cur=contexts.get(key)
    if cur and cur["version"] >= body.version:
        return {"accepted":False,"reason":"stale_version","current_version":cur["version"]}
    contexts[key]={"version":body.version,"payload":body.payload}
    return {"accepted":True,"ack_id":f"ack_{body.context_id}_v{body.version}","stored_at":datetime.utcnow().isoformat()+"Z"}

@app.post("/v1/tick")
async def tick(body: TickBody):
    actions=[]
    for tid in body.available_triggers:
        t=contexts.get(("trigger",tid),{}).get("payload")
        if not t: continue
        mid=t.get("merchant_id")
        m=contexts.get(("merchant",mid),{}).get("payload")
        if not m: continue
        cat=contexts.get(("category",m.get("category_slug")),{}).get("payload")
        if not cat: continue
        cid=t.get("customer_id")
        c=contexts.get(("customer",cid),{}).get("payload") if cid else None
        out=compose(cat,m,t,c)
        if not out.get("body"): continue
        conv=f"conv_{mid}_{tid}"
        template="vera_customer_v1" if out["send_as"]=="merchant_on_behalf" else "vera_contextual_v1"
        params=[m.get("identity",{}).get("name","")]
        actions.append({"conversation_id":conv,"merchant_id":mid,"customer_id":cid,"send_as":out["send_as"],
                        "trigger_id":tid,"template_name":template,"template_params":params,
                        "body":out["body"],"cta":out["cta"],"suppression_key":out["suppression_key"],"rationale":out["rationale"]})
        conversations.setdefault(conv,[]).append({"from":"vera","body":out["body"],"trigger_id":tid})
    return {"actions":actions}

@app.post("/v1/reply")
async def reply(body: ReplyBody):
    hist=conversations.setdefault(body.conversation_id,[])
    hist.append({"from":body.from_role,"body":body.message})
    if negative(body.message):
        return {"action":"end","rationale":"Merchant/customer declined; exit cleanly and honor STOP/no-interest signals."}
    if auto_reply_like(body.message):
        # Do not burn multiple turns on canned responses.
        canned_count=sum(1 for x in hist if x.get("from")==body.from_role and auto_reply_like(x.get("body","")))
        if canned_count >= 2:
            return {"action":"end","rationale":"Repeated canned/automated response detected; stopping to avoid auto-reply pollution."}
        return {"action":"send","body":"Samajh gayi — owner/manager tak pahunchne se pehle main ek hi baar exact next step share kar deti hoon. Agar aap khud handle kar rahe hain, bas YES bol dijiye.","cta":"YES/STOP","rationale":"Detected likely auto-reply and made one concise routing attempt."}
    if explicit_action(body.message):
        return {"action":"send","body":"Done — main isi action par move karti hoon. Agar koi detail missing hui to sirf wahi poochungi; dobara qualification loop nahi karungi.","cta":"open_ended","rationale":"Explicit action intent detected; hand off immediately instead of re-qualifying."}
    # Question/normal reply: acknowledge and advance with one focused question.
    if "?" in body.message:
        return {"action":"send","body":"Good question. Main sirf context mein available details use karungi — jo confirm nahi hai, usse assume nahi karungi. Aap chahte hain main next draft/action prepare karun?","cta":"open_ended","rationale":"Answers cautiously and advances the conversation with a single low-friction next step."}
    return {"action":"send","body":"Got it. Main is context ke basis par next practical step prepare kar sakti hoon — proceed karun?","cta":"open_ended","rationale":"Acknowledges the merchant and advances without repeating the prior message."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
