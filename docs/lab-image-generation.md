# v0.9.2開発素材の生成記録

使用方式: 組み込み `imagegen`。別API/CLIは使用していない。生成出力を作業リポジトリへコピーし、元のv0.9.1背景と人物・釜PNGは保持している。

| 採用素材 | 参照と用途 |
| --- | --- |
| `assets/little_laboratory_background.png` | 既存JPGを編集。背景のみ |
| `assets/props/lectern.png` | 新背景を画風参照。独立した書見台 |
| `assets/props/basket.png` | 新背景で生成後、外周透過を再編集した素材かご |
| `assets/props/tray.png` | 新背景を画風参照。独立した完成品トレー |

道具は実際のRGBA透過を確認済み。RGBに残る色と実表示の不透明領域は区別して検査した。描画時はalpha>=128の本体境界を使って透明余白を配置寸法から除き、元PNGの色は加工しない。

## 背景の最終プロンプト

```text
Use case: precise-object-edit. Edit target: the supplied 1280x853 pixel-art alchemist laboratory background, for a desktop game. Replace ONLY the desk and stool on the far RIGHT wall with a shallow wall-hugging bookcase, receding along the right wall. Remove the projecting desk, drawers beneath desk and stool completely; restore the wooden floor where they stood. Shelves contain books, small potion bottles, specimen jars and small storage boxes. Preserve the original central window, exterior view, hanging lighting, all left-side furniture, rug, plants, foreground corners, warm dusk palette and original crisp detailed pixel-art style, camera angle and framing. Bookshelf depth must stay shallow and not project into the central floor. The rug and center floor remain empty for independent game sprites. No characters, cauldrons, freestanding lecterns, baskets, workbenches or new desks. Deliver just the edited background at the same composition/aspect ratio, no labels or watermark.
```

## 書見台の最終プロンプト

```text
Use case: stylized-concept. Input image is STYLE REFERENCE ONLY. Generate one isolated game sprite asset: a small waist-high wooden alchemist lectern with an open cream-paged book on its angled top, dark walnut wood, subtle brass corners, two sturdy short feet. Match the reference's crisp warm detailed pixel-art, three-quarter front view slightly from above. The book faces toward a character standing to its left/front; visible pages contain tiny abstract ink marks, no readable text. Compact footprint, no chair or desk, no lamps or bottles. Entire object fully visible with generous transparent padding on all sides. Actual transparent RGBA background, no checkerboard illustration, no white outline or halo, no cast shadow. This is a foreground prop separate from the room. Only ONE lectern centered, no room or other objects. At 1024 square, keep the art crisp and readable when reduced to about 130x160 on screen.
```

## かごの生成・最終編集プロンプト

```text
Use case: stylized-concept. The input is STYLE REFERENCE ONLY. Make ONE standalone empty shallow woven wicker alchemist ingredient basket sprite for this pixel-art game. Warm tan brown wicker, dark interior, oval open top, two small side handles. Three-quarter front view from slightly above, matching the room perspective and warm detailed pixel-art style, readable when reduced to 100x65 pixels. Empty, with visible interior where animated herbs/crystals will be placed by code. Actual transparent RGBA background with generous padding, no room, no text, no white halo, no ground shadow, no other objects. Whole basket fully visible centered.
```

```text
Use case: background-extraction. EDIT this existing empty wicker basket sprite. Keep the exact basket design, perspective, colors and all handles. Remove ALL of the brown glow, shadow and fog outside the physical basket silhouette. Outside the woven object must be completely alpha=0, a sharp clean pixel-art cutout, no halo, no bloom, no feathered cast shadow, no floor. Transparent RGBA image. Whole object fully visible with clear transparent padding.
```

## トレーの最終プロンプト

```text
Use case: stylized-concept. Input is only pixel-art style reference. Create ONE small empty shallow rectangular wooden serving tray sprite, dark walnut brown with subtle brass corners and raised rim. This tray sits on the floor to hold a completed potion bottle in a cozy alchemist game. Three-quarter front view from above matching reference room, detailed crisp warm pixel art, compact 3:1 wide shallow proportions, no legs, no table. Entire tray centered on real TRANSPARENT RGBA background, all sides fully visible with generous transparent padding. No bottle yet, no room, no ground shadow, no white outlines, no text, no grid.
```

## 不採用の人物編集

既存5ポーズを一列に並べて外周マットだけを補正する生成と、市松模様を実透過へ置換する再編集を試した。出力はいずれも不透明背景を持ち、人物の細部にも変化があったため不採用。採用素材の輪郭補正には、ユーザー回答後にPythonを使用した。

元画像を維持する輪郭限定補正器は `scripts/refine_lab_sprites.py`。ユーザーの「必要に応じて画像を生成し変更を加えてください」という回答を受け、別フォルダーへ生成した候補を目視・画素検証して反映した。

一括生成だけの問題かを切り分けるため、既存idle.pngの1枚に絞った補正も実施した。出力は1254×1254のRGB画像で、市松模様が焼き込まれており不採用。人物編集は合計3回とも採用条件を満たしていない。

単体検証のプロンプト:

```text
Edit target: this SINGLE existing transparent pixel-art character sprite. Perform a minimal technical edge cleanup, not a redesign. Replace the unwanted pale gray/white matte around the outer silhouette with a clean dark warm pixel outline or real transparent edge. Preserve exactly the girl identity, eyes, face, hat with goggles, clothing, left-side held green bottle, pose, relative proportions, and every bright highlight inside the art. Keep the complete hat and all hands and feet. Output ONE centered sprite only, real PNG RGBA transparency with alpha=0 outside the sprite, including empty spaces between arm and body. No background, no white backdrop, no checkerboard illustration, no floor or cast shadow. Keep generous clear padding and the original low-resolution pixel style. Do not add detail or change facial expression.
```

## 採用した輪郭補正

v0.9.1のPNGを入力とし、背景に接する明るい中性色の縁だけを近傍の輪郭色で補正した。顔・服・瓶・釜の上部を保護し、保護対象51,168画素の一致を確認。輪郭3,196画素を補正し、接地から離れた微小な走査線ノイズ17画素を除去した。全身を切らずに足元を合わせ、釜は状態ごとの先頭コマの本体を共有する。湯気・口・火は各コマの動きを保持する。入力と出力のSHA256・移動量・固定領域は同梱のsprites_manifest.jsonに記録した。
