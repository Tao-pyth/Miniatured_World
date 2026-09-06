"""手元の採用原画を整形する。座標は原画上の検査済み接点であり入力情報ではない。"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path
from PIL import Image, ImageDraw

from audit_hand_sources import main as audit_sources, OUT
from build_walk_sprites import remove_background

ROOT = Path(__file__).resolve().parents[1]

# 共通128pxへ縮小後、手の内側で瓶の首/ページを把持する点。
GRIPS = {
 'read': [(47,80),(38,77),(32,72),(26,67),(27,69),(33,69),(33,69),(28,70),(34,73),(40,78),(47,80),(47,80)],
 'collect': [(43,88),(40,102),(40,115),(36,115),(35,116),(39,115),(37,115),(35,85),(36,86),(48,93),(44,86),(43,86)],
 'place': [(42,94),(46,94),(39,109),(26,117),(45,116),(34,116),(33,116),(28,116),(38,102),(40,97),(41,95),(40,96)],
 'collect-lower': [(41,95),(42,102),(41,113),(42,114),(43,116),(39,116)],
 'collect-rise': [(39,116),(40,113),(40,108),(40,100),(42,93),(41,87)],
 'mix-reach': [(51,87),(41,79),(30,74),(22,74),(26,72),(27,75),(28,76),(22,72),(26,73),(29,77),(28,79),(25,79),(28,72),(34,75),(40,79),(51,87)],
 'walk-empty': [(52,90)]*8,
}
NECKS = {
 'collect-lower': [(56,70),(56,76),(58,87),(55,91),(57,95),(57,98)],
 'collect-rise': [(52,96),(54,91),(55,86),(54,79),(56,71),(56,66)],
 'collect': [(61,64),(63,76),(65,87),(58,98),(51,98),(57,98),(55,98),(62,70),(53,81),(67,73),(61,64),(61,64)],
 'place': [(63,66),(65,66),(61,87),(56,97),(65,98),(58,98),(57,98),(54,98),(53,80),(64,71),(63,67),(62,65)],
}
RIGHT_WRISTS = {
 'read': [(80,76)]*12,
 'mix-reach': [(72,78)]*16,
 'walk-empty': [(82,87)]*8,
 'collect': [(69,73),(69,84),(76,92),(73,95),(68,96),(73,95),(72,95),(70,76),(66,85),(71,81),(68,74),(68,74)],
 'place': [(69,79),(71,79),(73,93),(73,95),(74,96),(72,95),(72,95),(70,95),(69,87),(69,82),(71,81),(78,90)],
 'collect-lower': [(71,85),(75,91),(78,97),(78,101),(78,106),(82,108)],
 'collect-rise': [(68,95),(70,92),(72,87),(70,87),(72,82),(75,77)],
}

def key(name: str, number: int) -> str:
    return f'{name}-{number:02}'

def remove_detached_pixels(frame: Image.Image) -> Image.Image:
    """原画の頭部置換で残った小さな孤立片を除く。斜めの輪郭は接続扱い。"""
    pixels=frame.load(); seen=set()
    for y in range(frame.height):
        for x in range(frame.width):
            if (x,y) in seen or not pixels[x,y][3]:
                continue
            queue=deque([(x,y)]); component=[]; seen.add((x,y))
            while queue:
                px,py=queue.popleft(); component.append((px,py))
                for dx,dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
                    nx,ny=px+dx,py+dy
                    if 0<=nx<frame.width and 0<=ny<frame.height and (nx,ny) not in seen and pixels[nx,ny][3]:
                        seen.add((nx,ny)); queue.append((nx,ny))
            if len(component)<12:
                for px,py in component:
                    pixels[px,py]=(0,0,0,0)
    return frame

# 同じ屈み原画の開いた手/閉じた手を反対方向に使い、取得と配置を対にする。
# 各系列内の原画の種類数もmanifestへ記録する。
COLLECT = [('collect',1),('place',1),('collect-lower',1),('collect-lower',2),('place',3),
           ('collect-lower',3),('collect-lower',4),('collect',4),('collect',7),
           *[('collect-rise',i) for i in range(1,7)],('collect',12)]
SERIES = {
 'read': [('read',i) for i in (1,10,2,3,6,7,5,4,8,9,10,11,12)],
 'collect': COLLECT,
 'mix': [('mix-reach',i) for i in (2,15,14,3,4,5,6,7,8,9,10,11,12,13,14,15)],
 'place': list(reversed(COLLECT)),
}
# 配置は把持したまま下ろし、開いた手で戻る。立位/復帰の専用原画も
# 採用し、全系列合計44種の原画を確保する（逆再生の重複は数えない）。
SERIES['place'][2]=('place',11)
SERIES['place'][12]=('place',9)

def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'logs/hand-motion-v0.9.5/candidate-assets')
    parser.add_argument('--adopt',action='store_true',help='既存の基礎素材へ追加し、製品manifestを更新する')
    args=parser.parse_args()
    audit_sources()
    args.output.mkdir(parents=True,exist_ok=True)
    manifest_path=args.output/'sprites_manifest.json' if args.adopt else ROOT/'src/miniatured_world/assets/sprites_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    palette=Image.new('P',(1,1)); colors=sum(manifest['palette'],[])
    palette.putpalette(colors+colors[:3]*(256-len(manifest['palette'])))
    records=[]
    metadata={'schema':1,'native_size':[128,128],'baseline':120,'series':{},'walking':[]}

    def save(frame, path):
        # 既に64色の切り抜きを再量子化すると、Pillowの色キャッシュにより
        # 近接色が変わる場合がある。手マスクの画素一致を保つ。
        allowed={tuple(c) for c in manifest['palette']}
        if {p[:3] for p in frame.get_flattened_data() if p[3]}<=allowed:
            quantized=frame.convert('RGBA')
        else:
            quantized=frame.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE).convert('RGBA')
        quantized.putalpha(frame.getchannel('A').point(lambda a:255 if a>=160 else 0))
        quantized.putdata([p if p[3] else (0,0,0,0) for p in quantized.get_flattened_data()])
        destination=args.output/path; destination.parent.mkdir(parents=True,exist_ok=True); quantized.save(destination)
        records.append({'path':path,'size':list(quantized.size),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
        return quantized

    # 共通の頭部は従来の歩行から継承。帽子・顔は切り欠かず全体を残す。
    head=Image.open(OUT/'walk-empty-01.png').convert('RGBA').crop((0,0,128,72))
    prepared={}
    for name, grips in GRIPS.items():
        for i,grip in enumerate(grips,1):
            raw=Image.open(OUT/f'{key(name,i)}.png').convert('RGBA')
            foot_region=raw.crop((48,100,92,128)).getbbox()
            foot_shift=120-(100+foot_region[3])
            if foot_shift:
                moved=Image.new('RGBA',(128,128)); moved.paste(raw,(0,foot_shift)); raw=moved
            grip=(grip[0],grip[1]+foot_shift)
            frame=raw.copy()
            # 一様な縮尺を保ち、頭部の生成差だけを共通原画に置換する。
            # 屈み原画では頭部の下がりと前傾位置をそのまま採用する。
            top=raw.getbbox()[1]
            neck=NECKS[name][i-1] if name in NECKS else (65,72 if name=='walk-empty' else 67)
            neck=(neck[0],neck[1]+foot_shift)
            dx=neck[0]-69; dy=neck[1]-70
            ImageDraw.Draw(frame).rectangle((0,0,127,neck[1]),fill=(0,0,0,0))
            # 頭部の横へ出る腕を保持する。上半分の矩形切り替えだけでは
            # 読書・注ぎの手が消えるため、原画の腕領域を先に復元する。
            gx,gy=grip
            arm_mask=Image.new('L',(128,128))
            ImageDraw.Draw(arm_mask).polygon([(gx-7,gy-7),(gx+8,gy-7),(60+dx,neck[1]),(61+dx,neck[1]+10),(gx+8,gy+7),(gx-7,gy+7)],fill=255)
            arm=Image.new('RGBA',(128,128)); arm.paste(raw,(0,0),arm_mask)
            if name in {'read','mix-reach'}:
                frame.alpha_composite(arm)
            frame.alpha_composite(head,(dx,dy))
            frame=remove_detached_pixels(frame)
            rw=RIGHT_WRISTS[name][i-1]
            prepared[key(name,i)]=(frame,grip,(rw[0],rw[1]+foot_shift),(dx,dy))

    durations={'read':1800,'collect':2200,'mix':3200,'place':2200}
    events={'read':{'touch':4,'release':8},'collect':{'grab':8},'mix':{'pour_start':6,'pour_end':8,'recover':12},'place':{'contact':7,'release':8}}
    angles=(0,0,0,0,-10,-35,-80,-100,-45,0,90,180,180,90,30,0)
    holds={
      'read':[100,100,100,100,200,150,150,150,150,100,100,100,300],
      'collect':[120]*7+[160,240]+[120]*6+[240],
      'mix':[125]*7+[375,125,725,125,350,250,125,125,125],
      'place':[120]*7+[240,200]+[120]*6+[200],
    }
    for action, sources in SERIES.items():
        frames=[]; entries=[]
        for index,(name,number) in enumerate(sources):
            source=key(name,number); frame,grip,right_wrist,head_offset=prepared[source]
            frame=frame.copy()
            if action in {'read','mix'}:
                # 両足を植えた作業。膝から下は同じ全身原画を使用する。
                legs=prepared['read-01'][0].crop((0,96,128,128))
                frame.paste(legs,(0,96))
            path=f'characters/alchemist_girl/{action}_{index+1:02}.png'
            frame=save(frame,path); frames.append(frame)
            # 指の前景は同じ原画の透明切り抜き。別の手を描き足さない。
            hand=Image.new('RGBA',(128,128)); x,y=grip
            area=(x-3,y-3,x+4,y+4); hand.paste(frame.crop(area),area[:2])
            mask=f'hands/{action}_{index+1:02}.png'; save(hand,mask)
            left_wrist=[x+2,y-4] if source=='collect-lower-04' else [x+4,y-2]
            entries.append({'sprite':path,'hand_mask':mask,'source':source,'grip':list(grip),
                            'left_wrist':left_wrist,'right_wrist':list(right_wrist),'head_offset':list(head_offset),
                            'feet':[[52,120],[74,120]],'opening_offset':[0,-2]})
        assert len(holds[action])==len(entries)
        assert sum(holds[action])==durations[action]
        for entry, duration in zip(entries,holds[action]):
            entry['duration_ms']=duration
        for i,entry in enumerate(entries):
            entry['vessel_angle']=angles[i] if action=='mix' else 0
        metadata['series'][action]={'duration_ms':durations[action],'unique_originals':len(set(sources)),'events':events[action],'frames':entries}
        board=Image.new('RGB',(1024,((len(frames)+3)//4)*280),'#383943')
        for index,frame in enumerate(frames):
            enlarged=frame.resize((256,256),Image.Resampling.NEAREST); pos=(index%4*256,index//4*280)
            board.paste(enlarged,pos,enlarged); ImageDraw.Draw(board).text((pos[0]+8,pos[1]+258),f'{action} {index+1:02}',fill='white')
        board.save(OUT.parent/f'{action}-candidate-frames.png')
    for i in range(1,9):
        carry,grip,right_wrist,head_offset=prepared['collect-12']
        # 取得の終端と同じ頭部・両腕を使う。持ち手を動かさず運び、
        # 腰より下で従来8コマの歩幅とコートの動きを保つ。
        frame=carry.copy()
        # 距離同期された既存の脚8コマを保存する。
        reference=args.output if args.adopt else ROOT/'src/miniatured_world/assets'
        old=Image.open(reference/f'characters/alchemist_girl/walk_{i:02}.png').convert('RGBA')
        frame.paste(old.crop((0,96,128,128)),(0,96))
        path=f'characters/alchemist_girl/carry_walk_{i:02}.png'; save(frame,path)
        metadata['walking'].append({'sprite':path,'hand_mask':'hands/collect_16.png','grip':list(grip),'left_wrist':[grip[0]+4,grip[1]-2],'right_wrist':list(right_wrist),'feet':[[54,120],[76,120]],'opening_offset':[0,-2]})
    bottles=remove_background(Image.open(ROOT/'art/hand-motion-v0.9.5/vials.png'))
    empty_vial=None
    for index,name in enumerate(('empty','filled')):
        cell=bottles.crop((index*bottles.width//2,0,(index+1)*bottles.width//2,bottles.height)); cell=cell.crop(cell.getbbox())
        frame=Image.new('RGBA',(24,32)); frame.paste(cell.resize((12,18),Image.Resampling.NEAREST),(6,6))
        if empty_vial is not None:
            for y in range(frame.height):
                for x in range(frame.width):
                    original=empty_vial.getpixel((x,y));current=frame.getpixel((x,y))
                    if y<16 or not current[3]:frame.putpixel((x,y),original)
            frame.putalpha(empty_vial.getchannel('A'))
        saved=save(frame,f'held/vial_{name}.png')
        if empty_vial is None:empty_vial=saved
    metadata['vial']={'grip':[12,10],'opening':[12,8],'base':[12,24],'size':[24,32]}
    (args.output/'hand_motion.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8',newline='\n')
    if args.adopt:
        paths={record['path'] for record in records}
        manifest['files']=[record for record in manifest['files'] if record['path'] not in paths]+records
        manifest['version']='0.9.5'
        manifest['hand_motion']={'metadata':'hand_motion.json','distinct_originals':44,'frames':{key:len(series['frames']) for key,series in metadata['series'].items()}}
        for source in sorted((ROOT/'art/hand-motion-v0.9.5').glob('*.png')):
            manifest['sources'][f'hand-motion-v0.9.5/{source.name}']=hashlib.sha256(source.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    else:
        (args.output/'hand_manifest.json').write_text(json.dumps({'files':records,'palette':manifest['palette']},indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'候補素材 {len(records)} PNG: {args.output}')

if __name__=='__main__':
    main()
