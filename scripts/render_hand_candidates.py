"""実背景上で原画・接点・前後マスクを確認する合成プレビュー。OS画面は取得しない。"""
from __future__ import annotations
import json
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication
from PIL import Image

from miniatured_world.app.lab_layout import DEFAULT_LAYOUT
from miniatured_world.app.lab_paint import draw_cauldron, load_props, shadow

ROOT=Path(__file__).resolve().parents[1]
CANDIDATES=ROOT/'logs/hand-motion-v0.9.5/candidate-assets'
OUTPUT=ROOT/'logs/hand-motion-v0.9.5/candidate-preview'
WORK={'read':(770,686),'collect':(714,744),'mix':(630,690),'place':(734,726)}
ANGLES=(0,0,0,0,-10,-35,-80,-100,-45,0,90,180,180,90,30,0)

def hand_position(action,frame):
    x,y=WORK[action]; gx,gy=frame['grip']
    return x+(64-gx if action in {'read','place'} else gx-64)*2,y+(gy-120)*2

def main():
    app=QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True,exist_ok=True)
    metadata=json.loads((CANDIDATES/'hand_motion.json').read_text())
    props=load_props()
    pot=QPixmap(str(ROOT/'src/miniatured_world/assets/cauldron/magic_cauldron/idle_01.png'))
    background=QImage(str(ROOT/'src/miniatured_world/assets/little_laboratory_background.png'))
    vial=QPixmap(str(CANDIDATES/'held/vial_filled.png'))

    def draw_sprite(painter,action,path):
        x,y=WORK[action]; sprite=QPixmap(str(CANDIDATES/path))
        painter.save();painter.translate(x,y)
        if action in {'read','place'}:painter.scale(-1,1)
        painter.drawPixmap(QRectF(-128,-240,256,256),sprite,QRectF(sprite.rect()));painter.restore()

    def draw_bottle(painter,x,y,angle=0):
        painter.save();painter.translate(x,y);painter.rotate(angle)
        painter.drawPixmap(QRectF(-24,-20,48,64),vial,QRectF(vial.rect()));painter.restore()

    def front(painter,key):
        item=DEFAULT_LAYOUT.gimmick(key);x,y=item.position;w,h=item.size
        sprite=pot if key=='cauldron' else props[key]
        if key=='cauldron':
            top=y-h*104/112; source_y=52
            painter.drawPixmap(QRectF(x-w/2,top+source_y*2,w,(112-source_y)*2),sprite,QRectF(0,source_y,96,112-source_y))
        else:
            ratio=.60 if key=='basket' else .625
            painter.drawPixmap(QRectF(x-w/2,y-h*(1-ratio),w,h*(1-ratio)),sprite,QRectF(0,sprite.height()*ratio,sprite.width(),sprite.height()*(1-ratio)))

    records={}
    for action,series in metadata['series'].items():
        previews=[]; records[action]=[]
        for index,frame in enumerate(series['frames']):
            stage=QImage(1280,853,QImage.Format.Format_RGB32); stage.fill(QColor('#383943'))
            p=QPainter(stage);p.drawImage(QRectF(0,0,1280,853),background);p.end()
            layer=QImage(640,427,QImage.Format.Format_ARGB32_Premultiplied);layer.fill(Qt.GlobalColor.transparent)
            p=QPainter(layer);p.scale(.5,.5)
            items=[(g.position[1],g.key) for g in DEFAULT_LAYOUT.gimmicks]+[(WORK[action][1],'character')]
            for _,key in sorted(items):
                if key=='character':
                    x,y=WORK[action];shadow(p,x,y-2,130);draw_sprite(p,action,frame['sprite'])
                elif key=='cauldron':draw_cauldron(p,DEFAULT_LAYOUT,pot)
                else:
                    item=DEFAULT_LAYOUT.gimmick(key);x,y=item.position;w,h=item.size
                    shadow(p,x,y-2,w*.8);p.drawPixmap(QRectF(x-w/2,y-h,w,h),props[key],QRectF(props[key].rect()))
            hx,hy=hand_position(action,frame)
            if action=='read':
                if 4<=index<=8:
                    p.setPen(QPen(QColor('#a88a59'),2));p.setBrush(QColor('#f0dfad'))
                    # 左ページの角をつまんで中央へ持ち上げる。
                    p.drawPolygon(QPolygonF([QPointF(848,566),QPointF(hx,hy-18),QPointF(hx,hy),QPointF(842,594)]))
                    draw_sprite(p,action,frame['hand_mask'])
            else:
                angle=ANGLES[index] if action=='mix' else 0
                if action=='collect' and index<8:
                    draw_bottle(p,660,736)
                elif action=='place' and index>=8:
                    draw_bottle(p,788,718)
                else:
                    draw_bottle(p,hx,hy,angle)
                draw_sprite(p,action,frame['hand_mask'])
                if action=='collect':front(p,'basket')
                elif action=='place':front(p,'product')
                elif 10<=index<=13:front(p,'cauldron')
            p.end();p=QPainter(stage);p.drawImage(QRectF(0,0,1280,854),layer);p.end()
            path=OUTPUT/f'{action}-{index+1:02}.png';stage.save(str(path))
            image=Image.open(path).convert('RGB'); crop=image.crop((430,440,970,790)).resize((810,525),Image.Resampling.NEAREST)
            previews.append(crop)
            records[action].append({'frame':index+1,'grip_stage':[hx,hy],'angle':ANGLES[index] if action=='mix' else 0})
        # 全コマで同じGIFパレットを使い、量子化による輪郭ちらつきを抑える。
        palette=previews[len(previews)//2].quantize(colors=256)
        frames=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in previews]
        durations=[f['duration_ms'] for f in series['frames']]
        for speed in (1,2):
            frames[0].save(OUTPUT/f'{action}-{"normal" if speed==1 else "slow"}.gif',save_all=True,append_images=frames[1:],duration=[d*speed for d in durations],loop=0)
    (OUTPUT/'contacts.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    print(OUTPUT)

if __name__=='__main__':main()
