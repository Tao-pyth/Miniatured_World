"""原画候補の数値・画像検査。未達を成功扱いせずJSONと終了コードへ反映する。"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'logs/hand-motion-v0.9.5/candidate-assets'

def main():
    metadata=json.loads((ASSETS/'hand_motion.json').read_text())
    manifest=json.loads((ASSETS/'hand_manifest.json').read_text())
    palette={tuple(c) for c in manifest['palette']}
    issues=[]; results={}; all_originals=set()
    for record in manifest['files']:
        path=ASSETS/record['path'];im=Image.open(path).convert('RGBA');colors=set(im.get_flattened_data());bounds=im.getbbox()
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:issues.append(f'{path.name}: hash')
        if any(p[3] not in (0,255) or (p[3] and p[:3] not in palette) for p in colors):issues.append(f'{path.name}: palette/alpha')
        if not bounds or min(bounds[0],bounds[1],im.width-bounds[2],im.height-bounds[3])<4:issues.append(f'{path.name}: margin')
    for action,series in metadata['series'].items():
        frames=series['frames']; measured={}
        distinct=set()
        for frame in frames:
            im=Image.open(ASSETS/frame['sprite']).convert('RGBA');digest=hashlib.sha256(im.tobytes()).hexdigest();distinct.add(digest);all_originals.add(digest)
            for joint in ('grip','left_wrist','right_wrist'):
                if not im.getpixel(tuple(frame[joint]))[3]:issues.append(f'{frame["sprite"]}: {joint} off silhouette')
            for x,y in frame['feet']:
                if not any(im.getpixel((x,yy))[3] for yy in (y-2,y-1)):issues.append(f'{frame["sprite"]}: foot contact drift')
            hand=Image.open(ASSETS/frame['hand_mask']).convert('RGBA')
            if any(h[3] and h!=p for h,p in zip(hand.get_flattened_data(),im.get_flattened_data())):issues.append(f'{frame["sprite"]}: hand mask mismatch')
        for joint in ('grip','left_wrist','right_wrist'):
            maximum=max(math.dist(a[joint],b[joint]) for a,b in zip(frames,frames[1:]));measured[joint]=maximum
            if maximum>8:issues.append(f'{action}: {joint} step {maximum:.3f} > 8')
        minimum=8 if action=='read' else 12
        if not minimum<=len(distinct)<=16:issues.append(f'{action}: distinct original poses {len(distinct)}')
        if len(frames)>16 or sum(f['duration_ms'] for f in frames)!=series['duration_ms']:issues.append(f'{action}: frame timing')
        results[action]={'frames':len(frames),'distinct_pngs':len(distinct),'max_joint_step':measured,'duration_ms':series['duration_ms']}
    empty=Image.open(ASSETS/'held/vial_empty.png');full=Image.open(ASSETS/'held/vial_filled.png')
    if empty.getchannel('A').tobytes()!=full.getchannel('A').tobytes():issues.append('vial silhouette changes with contents')
    if len(all_originals)<44:issues.append(f'all actions: only {len(all_originals)} distinct original poses')
    report={'passed':not issues,'png_count':len(manifest['files']),'distinct_originals':len(all_originals),'series':results,'issues':issues,
            'limits':'画像全体の自然さ、実背景上の重なり、動作連携の最終合格は別途目視とQt結合検査を要する。'}
    (ASSETS.parent/'candidate-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(bool(issues))

if __name__=='__main__':main()
