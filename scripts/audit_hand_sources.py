"""手元原画の未補正コマを共通縮尺で検査する（製品素材は変更しない）。"""
from pathlib import Path
import json
from PIL import Image, ImageDraw
from build_walk_sprites import remove_background

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'logs/hand-motion-v0.9.5/source-audit'
SPECS = {
    'read': ((0,315,615,919,1254), (0,410,800,1254), 104/306),
    'collect': ((0,256,512,768,1024), (0,520,1024,1536), 104/389),
    'mix': ((0,314,627,940,1254), (0,314,610,913,1254), 104/258),
    'place': ((0,362,724,1086,1448), (0,385,680,1086), 104/310),
    'collect-lower': ((0,512,1024,1536), (0,540,1024), .22),
    'collect-rise': ((0,512,1024,1536), (0,460,1024), .20),
    'mix-reach': ((0,314,627,940,1254), (0,314,610,913,1254), 104/258),
    'walk-empty': ((0,400,750,1110,1536), (0,500,1024), 104/384),
}
CENTERS = {
    'collect-lower': (337,770,1214,327,759,1210),
    'collect-rise': (303,791,1267,306,798,1273),
    'walk-empty': (192,548,904,1262,184,540,896,1254),
}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT/'src/miniatured_world/assets/sprites_manifest.json').read_text())
    palette = Image.new('P',(1,1)); colors = sum(manifest['palette'], [])
    palette.putpalette(colors + colors[:3]*(256-len(manifest['palette'])))
    records = {}
    for name, (columns, rows, scale) in SPECS.items():
        path=ROOT/f'art/hand-motion-v0.9.5/{name}-sheet.png'
        if not path.exists():
            path=ROOT/f'art/hand-motion-v0.9.5/{name}.png'
        sheet = remove_background(Image.open(path))
        count=len(columns)-1
        board = Image.new('RGB', (count*256, (len(rows)-1)*280), '#383943')
        frames=[]; records[name]=[]
        for row in range(len(rows)-1):
            for col in range(count):
                cell=sheet.crop((columns[col],rows[row],columns[col+1],rows[row+1]))
                box=cell.getbbox(); left,top,right,bottom=box
                # 下端の手に引っ張られないよう、靴の大きい連結領域から接地を求める。
                foot=cell.crop((int(cell.width*.30), max(top,bottom-30), cell.width, bottom))
                footbox=foot.getbbox()
                center=int(cell.width*.30)+(footbox[0]+footbox[2])/2
                if name in CENTERS:
                    center=CENTERS[name][row*count+col]-columns[col]
                cropped=cell.crop(box)
                cropped=cropped.resize((round(cropped.width*scale),round(cropped.height*scale)),Image.Resampling.NEAREST)
                x=64-round((center-left)*scale); y=120-cropped.height
                native=Image.new('RGBA',(128,128)); native.paste(cropped,(x,y))
                result=native.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE).convert('RGBA'); result.putalpha(native.getchannel('A'))
                number=row*count+col+1
                result.save(OUT/f'{name}-{number:02}.png'); frames.append(result)
                board.paste(result.resize((256,256),Image.Resampling.NEAREST),(col*256,row*280),result.resize((256,256),Image.Resampling.NEAREST))
                ImageDraw.Draw(board).text((col*256+8,row*280+256),f'{name} {number:02}',fill='white')
                records[name].append({'cell':[columns[col],rows[row],columns[col+1],rows[row+1]],'bounds':list(box),'center':center,'offset':[x,y],'scale':scale})
        board.save(OUT/f'{name}-frames.png')
        previews=[]
        for frame in frames:
            bg=Image.new('RGB',(512,512),'#383943'); enlarged=frame.resize((512,512),Image.Resampling.NEAREST); bg.paste(enlarged,(0,0),enlarged); previews.append(bg)
        previews[0].save(OUT/f'{name}-raw.gif',save_all=True,append_images=previews[1:],duration=170,loop=0)
    (OUT/'sources.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    main()
