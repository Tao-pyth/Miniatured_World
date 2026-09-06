# 歩行素材 v0.9.4

`walk-sheet.png` は imagegen で生成・修正した採用原画です。既存少女を参照し、4列×2行の8コマを生成しました。生成結果の市松背景を外縁から除き、顔・帽子の固定、接地、既存64色への変換、後半の脚の明暗調整を `scripts/build_walk_sprites.py` で再現します。生成AI自体の同一結果は保証せず、保存原画からPNGを再現できます。

## 初回プロンプト

```text
Create one production game sprite sheet: EXACTLY eight distinct sequential walking animation frames of the SAME alchemist girl in the reference. Grid exactly 4 columns x 2 rows, equal 384x512 cells, total1536x1024. Each cell contains one complete full-body character with generous transparent margin; no labels, numbers, dividers, ground shadows or text. Real transparent RGBA background. All eight face screen LEFT in a consistent three-quarter side view. Preserve the reference identity: ash blonde bob, teal eyes, oversized burgundy brown pointed witch hat with brass goggles, cream sleeves, teal vest, burgundy gold-trimmed long coat, brown shorts/trousers, dark brown buckled boots, small green flask held securely in forward hand. Exact same scale, hat design, face, palette and pixel density in every frame. Crisp deliberately clustered 16-bit pixel art, hard pixel edges, no white halo. 8-frame ordinary calm WALK cycle, not running or marching: top row 1 left foot forward heel contact/right foot rear toe push; 2 weight down with left knee bending and right heel lifting; 3 passing pose right knee crossing under hips left leg supports; 4 up pose right foot swings ahead left heel lifts; bottom row 5 right foot forward contact/left rear toe push; 6 weight down right knee bending left heel lifting; 7 passing left knee crossing under hips right supports; 8 up pose left foot ahead right heel lifts. DISTINCT alternating legs must visibly change every frame; near leg light, far leg shaded. Arms/coat counter-swing subtly; no changing identity or random hand gestures. Head and hat remain essentially identical, slight natural 1-pixel body bob only. Consistent foot-ground baseline in every cell, grounded supporting boot, free boot lifts. Center hip x in each cell exactly same. Frame order left-to-right then top-to-bottom. Anatomically two legs/two arms each. Keep entire hat, hands, flask, boots inside every cell.
```

参照: `art/pixel-v0.9.3/character-sheet.png`。初回原画は `reference-walk-sheet.png`。

## 採用原画への修正プロンプト

```text
EDIT this 8-frame sprite sheet. Preserve character identity, upper body, 4x2 layout, size, pixel-art style, and transparent background. CRITICAL CORRECTION: all eight existing leg poses look alike. Replace only lower body and legs with a REAL sequential eight-frame WALK cycle. She walks screen LEFT. Her NEAR leg (viewer-facing/light brown, front layer) MUST alternate from far LEFT of hips to far RIGHT of hips; her FAR leg (darker/rear layer) does opposite. Frame1(top-left): NEAR boot x=-32 px, FAR boot x=+32 px relative hips, both touch ground. Frame2: NEAR boot x=-18 on ground, FAR boot x=+20 lifted. Frame3: NEAR boot x=0 on ground, FAR knee lifted forward x=-12, far boot x=+8. Frame4: NEAR boot x=+18 on ground, FAR boot x=-24 lifted. Frame5(bottom-left): NEAR boot x=+32 on ground BEHIND BODY, FAR boot x=-32 on ground AHEAD BODY. Frame6: NEAR boot x=+20 lifted, FAR boot x=-18 on ground. Frame7: NEAR knee lifted forward x=-12 and boot x=+8, FAR boot x=0 on ground. Frame8: NEAR boot x=-24 lifted, FAR boot x=+18 on ground. Boots point LEFT, knees bend naturally. Distinct contact/down/pass/up frames. Frames 1 and5 MUST reverse which leg is ahead. Frames3and7 MUST have boots close together under hips, contrasting wide contact1/5. Maintain only TWO legs per pose. Preserve entire upper body and style, no labels, no text, no extra objects. Use real alpha transparency, not a checkerboard painted into pixels.
```

参照: 初回原画。採用原画は1536×1024のRGB画像で市松模様を含んだため、変換時に透過へ補正しています。
