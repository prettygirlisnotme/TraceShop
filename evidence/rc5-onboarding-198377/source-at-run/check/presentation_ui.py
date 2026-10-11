import json,os,time
from pathlib import Path
from native_shop_driver import Bridge,Driver

# Focused first-use onboarding UI check for native/traceshop-onboarding. Reuses the
# same official RC5 shell, real Store install and loopback bridge as the
# upstream-alignment harness (this directory carries a copy of the shared
# native_shop_driver/Store driver). Zero model requests, no video; exactly one
# first-screen diagnostic PNG via GET /g?raw=1.
#
# Scope: after the real Store install and open, click the new onboarding preset
# (quote_tradeoff_preset) and verify the catalog label + three defined inputs, that
# nothing auto-researches / starts an Agent / generates a proposal, that research then
# shows the budget-20 decision, that an explicit budget-23 re-research makes M240
# selectable and that the confirm button stays visible on the first proposal screen.
# The makepad bridge exposes visible widgets only, so candidate/proposal emptiness is
# read through read-only navigation. The agent_task_active guard branch of
# fill_quote_tradeoff is NOT exercised here (no model).
run=Path(os.environ["RC1_RUN"])
b=Bridge(int(os.environ["RC1_PORT"]))
driver=Driver(b,str(run),str(run/"unused-frames"),os.environ["RC1_APP_DATA"],"traceshop.shopping")
frame=b.get('/g?raw=1')
driver.window_w=int.from_bytes(frame[16:20],'big')
driver.window_h=int.from_bytes(frame[20:24],'big')
del frame

result={"kind":"onboarding-first-use-ui","model_requests":0,"video_recorded":False,
        "scope":"Official unmodified RC5, real Store install, scripted UI clicks only. No model, no fixture relay, no native tool-approval claim. Only fill_quote_tradeoff's non-active branch is exercised; the agent_task_active guard is NOT run-verified here.",
        "checks":{},"errors":[],"window_size":[driver.window_w,driver.window_h]}
def check(name,value):
    result["checks"][name]=bool(value)
    if not value:raise RuntimeError("check failed: "+name)
def click(name):
    if not driver.click(name,wait=.4):raise RuntimeError("cannot click "+name)
def text(name):return b.text(name) or ""
def fill(name,value):driver.clear_and_type(name,value,None)
def wait_text(name,needle,timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if needle in text(name):return True
        time.sleep(.3)
    return False
def find_card(needle):
    # Locate the candidate card that actually carries the item, do not assume card0.
    for i in range(3):
        if needle in text("cand%d_info"%i):return i
    return -1
def cand_texts():
    return [text("cand%d_info"%i) for i in range(3)]
def agent_running():
    return "未开始" not in text("agent_task_status")
def go(nav,page_marker):
    click(nav)
    time.sleep(.35)
    return page_marker in text("stage_info")

try:
    # --- before the new button: fresh first screen, nothing generated ---
    check("on_first_screen_before","1 / 4" in text("stage_info"))
    check("no_draft_before_button",not driver.draft_exists())
    check("agent_not_running_before_button",not agent_running())
    # Read-only navigation: prove there is no auto-generated candidate/proposal yet.
    go("nav_candidates","2 / 4")
    before_cands=cand_texts()
    result["candidates_before_button"]=before_cands
    check("no_candidates_before_button",all(c.strip()=="" for c in before_cands))
    go("nav_proposal","3 / 4")
    result["proposal_state_before_button"]=text("proposal_state")
    check("no_proposal_before_button","尚未生成提案" in text("proposal_state"))
    go("nav_input","1 / 4")

    # --- click the new onboarding preset: switch catalog + fill conditions only ---
    click("quote_tradeoff_preset")
    time.sleep(0.6)
    result["catalog_source_label"]=text("catalog_source_label")
    result["need_input"]=text("need_input")
    result["budget_input"]=text("budget_input")
    result["keywords_input"]=text("keywords_input")
    result["research_status_after_preset"]=text("research_status")
    check("official_snapshot_label","官网报价快照" in text("catalog_source_label"))
    check("need_value_defined",text("need_input")=="办公用无线鼠标，安静")
    check("budget_value_defined",text("budget_input")=="20")
    check("keywords_value_defined",text("keywords_input")=="wireless")

    # Still on the first screen; no draft, no auto Agent start.
    check("still_first_screen","1 / 4" in text("stage_info"))
    check("no_draft_after_button",not driver.draft_exists())
    check("agent_not_running_after_button",not agent_running())

    # Exactly one first-screen diagnostic PNG, straight from the bridge.
    driver.shot("onboarding-first-screen.png")

    # Read-only navigation: the click must not have generated candidates/proposal.
    go("nav_candidates","2 / 4")
    after_cands=cand_texts()
    result["candidates_after_button"]=after_cands
    check("no_candidates_after_button",all(c.strip()=="" for c in after_cands))
    go("nav_proposal","3 / 4")
    result["proposal_state_after_button"]=text("proposal_state")
    check("no_proposal_after_button","尚未生成提案" in text("proposal_state"))
    go("nav_input","1 / 4")

    # --- only now does the user click 研究商品 (rules only, still no model) ---
    click("research_btn")
    time.sleep(0.8)
    summary20=text("decision_summary")
    result["summary_at_budget_20"]=summary20
    check("budget20_official_snapshot_note","官网报价快照" in summary20)
    check("budget20_feasible_m170_1499","M170" in summary20 and "14.99" in summary20)
    check("budget20_quiet_evidence_gap","静音" in summary20 and "未证实" in summary20)
    check("budget20_higher_alt_m240_2299",
          "M240" in summary20 and "22.99" in summary20 and "超出预算" in summary20)
    check("no_draft_after_research_budget20",not driver.draft_exists())

    # --- user explicitly changes the budget to 23 and researches again ---
    click("nav_input")
    fill("budget_input","23")
    click("research_btn")
    time.sleep(0.8)
    result["summary_at_budget_23"]=text("decision_summary")

    # M240 becomes a selectable candidate at budget 23.
    card=find_card("M240")
    result["m240_card_index"]=card
    check("m240_selectable_at_budget_23",card>=0 and "22.99" in text("cand%d_info"%card))
    click("cand%d_btn"%card)
    time.sleep(0.8)
    wait_text("proposal_summary","选择摘要",8)

    # The confirm button must remain visible on the first proposal screen.
    c_confirm=driver.rect_center("confirm_btn")
    result["confirm_rect"]=(c_confirm or [None,None,None])[2]
    result["confirm_in_view"]=driver.in_view(c_confirm)
    check("confirm_visible_on_first_proposal_screen",bool(c_confirm) and driver.in_view(c_confirm))

    # No save and no model request: the draft must still be absent after selecting.
    result["proposal_summary_before_no_save"]=text("proposal_summary")
    result["no_draft_after_select"]=not driver.draft_exists()
    check("no_save_no_draft_after_select",not driver.draft_exists())
except Exception as error:
    result["errors"].append(repr(error))
    (run/"onboarding-ui-on-error.json").write_bytes(b.snap_raw())
    result["ui_on_error"]={k:text(k) for k in
        ("catalog_source_label","need_input","budget_input","keywords_input","research_status",
         "decision_summary","stage_info","proposal_summary","proposal_state","agent_task_status")}
result["passed"]=bool(result["checks"]) and all(result["checks"].values()) and not result["errors"]
(run/"onboarding-ui-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"passed":result["passed"],"checks":result["checks"],"errors":result["errors"]},ensure_ascii=False))
raise SystemExit(0 if result["passed"] else 4)
