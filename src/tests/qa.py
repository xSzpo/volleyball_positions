from playwright.sync_api import sync_playwright
import random, itertools, re, json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

random.seed(7)
FAIL=[]
def fail(m):
    FAIL.append(m); print("FAIL:",m, flush=True)
URL=(ROOT/'index.html').as_uri()
ROLES=['MB1','MB2','OH1','OH2','OP','S','L']

def vis_en(pg,sel):
    l=pg.locator(sel)
    return l.count()>0 and l.first.is_visible() and l.first.is_enabled()

def tap(pg,svg,x=None,y=None):
    box=pg.locator(svg).bounding_box()
    x=random.random() if x is None else x; y=random.random() if y is None else y
    pg.mouse.click(box['x']+box['width']*x, box['y']+box['height']*y)

def check_page(pg,ctx):
    t=pg.inner_text('body')
    if re.search(r'\bundefined\b|\bNaN\b|\[object|\bnull\b',t): fail(f"{ctx}: bad text in page")
    w=pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    if w>1: fail(f"{ctx}: horizontal overflow {w}px")

def play_match(pg,ctx,answer='random',maxsteps=200):
    """Play until end. At every state some forward control must exist."""
    n=0
    while n<maxsteps:
        n+=1
        if pg.is_visible('#gEnd'): return True
        if vis_en(pg,'#gnb button:enabled'):
            btns=pg.locator('#gnb button:enabled'); btns.nth(random.randrange(btns.count())).click(); continue
        if vis_en(pg,'#gNext'): pg.click('#gNext'); continue
        if pg.locator('#gOff').is_enabled():
            r=random.random()
            if r<.15 and pg.locator('#gHelp').is_enabled(): pg.click('#gHelp'); continue
            if r<.35: pg.click('#gOff'); continue
            tap(pg,'#courtG'); continue
        fail(f"{ctx}: STUCK in match at {pg.inner_text('#gTitle')} / {pg.inner_text('#gStepName')}"); return False
    fail(f"{ctx}: match did not finish in {maxsteps} actions"); return False

def drill_steps(pg,ctx,k=30):
    for i in range(k):
        if vis_en(pg,'#dnb button:enabled'):
            b=pg.locator('#dnb button:enabled'); b.nth(random.randrange(b.count())).click(); continue
        if vis_en(pg,'#nextBtn'): pg.click('#nextBtn'); continue
        if pg.locator('#offBtn').is_enabled():
            (pg.click('#offBtn') if random.random()<.3 else tap(pg,'#courtD')); continue
        fail(f"{ctx}: STUCK in drill at {pg.inner_text('#dq')}"); return

with sync_playwright() as p:
    b=p.chromium.launch()
    import sys
    cfg={'m':[({'width':390,'height':844},True,'light')],'d':[({'width':1280,'height':900},False,'dark')]}[sys.argv[1] if len(sys.argv)>1 else 'm']
    for vp,mobile,scheme in cfg:
      if True:
        ctxb=b.new_context(viewport=vp,is_mobile=mobile,has_touch=mobile,color_scheme=scheme,accept_downloads=True)
        pg=ctxb.new_page(); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto(URL); pg.wait_for_timeout(300); print('start',flush=True)
        tag=f"[{vp['width']} {scheme}]"
        check_page(pg,tag+" initial")
        # LEARN: every role/rotation/phase, both rules
        for rm in ['official','drill']:
            pg.click(f'[data-rm="{rm}"]')
            for role in ROLES:
                pg.click(f'.role[data-r="{role}"]')
                for i in range(6):
                    pg.click(f'.rot[data-i="{i}"]')
                    for ph in ['start','rec','ar','serve']:
                        pg.click(f'.ph[data-k="{ph}"]')
                        cue=pg.inner_text('#cue')
                        if not cue.strip(): fail(f"{tag} empty cue {role} R{i+1} {ph}")
                check_page(pg,f"{tag} learn {rm} {role}")
        # keyboard nav
        pg.click('.rot[data-i="0"]'); pg.keyboard.press('ArrowLeft')
        if pg.get_attribute('.rot[data-i="5"]','aria-pressed')!='true': fail(f"{tag} ArrowLeft wrap failed")
        pg.keyboard.press('ArrowRight')
        print('# DRILL all roles',flush=True)
        # DRILL all roles, visibility modes, neighbour on/off, rules modes
        pg.click('#tabDrill')
        for rm in ['official','drill']:
            pg.click(f'[data-rm="{rm}"]')
            for role in ROLES:
                pg.click(f'.role[data-r="{role}"]')
                for v in ['none','ref','all']:
                    pg.click(f'.vis[data-vis="drill"] button[data-v="{v}"]')
                    if random.random()<.5: pg.click('#nbDrill')
                    drill_steps(pg,f"{tag} drill {rm} {role} {v}",12)
                check_page(pg,f"{tag} drill {role}")
        # switch role mid neighbour-check
        pg.click('.role[data-r="OH1"]')
        for i in range(40):
            if 'Reception' in pg.inner_text('#dq') and pg.locator('#offBtn').is_enabled(): break
            drill_steps(pg,tag+" seek",1)
        if not pg.is_checked('#nbDrill'): pg.click('#nbDrill')
        tap(pg,'#courtD',.5,.7)
        pg.click('.role[data-r="MB1"]')
        drill_steps(pg,f"{tag} drill after role switch mid-check",5)
        # tab switch mid-check and back
        pg.click('.role[data-r="OH2"]')
        for i in range(40):
            if 'Reception' in pg.inner_text('#dq') and pg.locator('#offBtn').is_enabled(): break
            drill_steps(pg,tag+" seek",1)
        tap(pg,'#courtD',.5,.7); pg.click('#tabLearn'); pg.click('#tabDrill')
        drill_steps(pg,f"{tag} drill after tab switch mid-check",5)
        # review flow
        for i in range(40): drill_steps(pg,tag+" build misses",1)
        if pg.is_visible('#reviewBtn'):
            if vis_en(pg,'#nextBtn') is False and vis_en(pg,'#dnb button:enabled'): pg.locator('#dnb button').last.click()
            pg.click('#reviewBtn')
            for i in range(40):
                if pg.inner_text('#dq')=='Review done': break
                drill_steps(pg,tag+" review",1)
            if pg.inner_text('#dq')!='Review done': fail(f"{tag} review did not finish")
            else:
                pg.click('#nextBtn'); drill_steps(pg,tag+" after review",4)
        else: fail(f"{tag} review button never appeared")
        pg.click('#resetBtn'); drill_steps(pg,tag+" after reset",3)
        print('# MATCH: all step combos',flush=True)
        # MATCH: all step combos, orders, nb on/off
        pg.click('#tabGame')
        steps=['start','rec','ar','serve']
        combos=[c for r in range(1,5) for c in itertools.combinations(steps,r)]
        for ci,combo in enumerate(combos):
            role=ROLES[ci%7]; pg.click(f'.role[data-r="{role}"]')
            if pg.is_visible('#gSettings'): pg.click('#gSettings')
            for s_ in steps:
                if pg.is_checked(f'#gs-{s_}')!=(s_ in combo): pg.click(f'#gs-{s_}')
            pg.check(f'input[name="gOrder"][value="{"mixed" if ci%2 else "order"}"]')
            if random.random()<.5: pg.click('#nbGame')
            pg.click(f'.vis[data-vis="game"] button[data-v="{random.choice(["none","ref","all"])}"]')
            pg.click(f'[data-rm="{random.choice(["official","drill"])}"]')
            if pg.is_visible('#gSettings'): pg.click('#gSettings')
            pg.click('#gStart')
            exp=len(combo)*6
            sn=pg.inner_text('#gStepName'); m=re.search(r'of (\d+)',sn)
            if not m or int(m.group(1))!=exp: fail(f"{tag} combo {combo}: expected {exp} moments, got {sn}")
            ok=play_match(pg,f"{tag} match {combo} {role}")
            if ok:
                check_page(pg,f"{tag} match end {combo}")
                if pg.is_visible('#gReplay'):
                    pg.click('#gReplay'); play_match(pg,f"{tag} replay {combo}")
                pg.click('#gAgain'); 
                # quit mid-match
                for i in range(3):
                    if vis_en(pg,'#gNext'): pg.click('#gNext')
                    elif pg.locator('#gOff').is_enabled(): tap(pg,'#courtG')
                pg.click('#gQuit')
                if not pg.is_visible('#gSetup'): fail(f"{tag} quit did not return to setup")
        # no steps selected -> start disabled
        for s_ in steps:
            if pg.is_checked(f'#gs-{s_}'): pg.click(f'#gs-{s_}')
        if pg.locator('#gStart').is_enabled(): fail(f"{tag} start enabled with no steps")
        for s_ in steps: pg.click(f'#gs-{s_}')
        # role / rules change mid match
        pg.click('#gStart'); tap(pg,'#courtG'); pg.click('.role[data-r="S"]')
        if not pg.is_visible('#gSetup'): fail(f"{tag} role change mid-match didn't reset")
        pg.click('#gStart'); pg.click('[data-rm="drill"]')
        if not pg.is_visible('#gSetup'): fail(f"{tag} rules change mid-match didn't reset")
        pg.click('#gStart'); pg.click('#tabSets'); pg.click('#tabGame')
        play_match(pg,f"{tag} match after tab switch")
        # change vis mid match
        pg.click('#gAgain'); pg.click('.vis.compact button[data-v="all"]'); play_match(pg,f"{tag} match vis change")
        print('# SETS',flush=True)
        # SETS
        pg.click('#tabSets')
        for s_ in ['1','0','2','Shoot','4','Po','Til','7','6']:
            pg.click(f'#setchips button[data-s="{s_}"]')
        for i in range(12):
            btns=pg.locator('#setanswers button:enabled')
            if btns.count(): btns.nth(random.randrange(btns.count())).click()
            if vis_en(pg,'#snext'): pg.click('#snext')
            else: fail(f"{tag} sets quiz: no next"); break
        check_page(pg,f"{tag} sets")
        print('# DOWNLOADS',flush=True)
        # DOWNLOADS
        for k in ['schema','sets']:
            try:
                with pg.expect_download(timeout=5000) as d: pg.click(f'[data-dl="{k}"]')
                path=d.value.path(); data=open(path,'rb').read(5)
                if data!=b'%PDF-': fail(f"{tag} download {k} not a PDF")
            except Exception as e: fail(f"{tag} download {k} failed: {e}")
        print('# PERSISTENCE',flush=True)
        # PERSISTENCE after reload
        pg.click('#tabLearn'); pg.click('.role[data-r="OP"]'); pg.click('[data-rm="drill"]'); pg.click('#tabDrill'); pg.click('.vis[data-vis="drill"] button[data-v="ref"]')
        pg.reload(); pg.wait_for_timeout(300)
        if pg.get_attribute('.role[data-r="OP"]','aria-pressed')!='true': fail(f"{tag} role not remembered")
        if pg.get_attribute('[data-rm="drill"]','aria-checked')!='true': fail(f"{tag} rules mode not remembered")
        if pg.get_attribute('.vis[data-vis="drill"] button[data-v="ref"]','aria-checked')!='true': fail(f"{tag} drill vis not remembered")
        pg.click('[data-rm="official"]')
        if errs: fail(f"{tag} JS errors: {errs[:3]}")
        ctxb.close()
    b.close()
print("\nTOTAL FAILURES:",len(FAIL))
