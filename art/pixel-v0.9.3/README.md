# v0.9.3 ドット絵原画と生成プロンプト

組み込みimagegenで生成。外部API/CLIへの切替なし。以下の原画を `scripts/build_pixel_assets.py` で論理寸法/64色/透過へ整形する。再生成による画素一致は保証しないが、同梱原画からの整形はSHA256で検証できる。原画は配布exeへ同梱しない。

## character-sheet.png

参照: v0.9.2のcharacters/alchemist_girl/idle.png（特徴の参照）。採用はidle/success/failure/rest。workは後述の単体原画へ差し替え。

```text
Use case: style-transfer. Asset type: one production sprite sheet of this same alchemist girl. Remake her as crisp authentic low-resolution 16-bit RPG PIXEL ART, not a painted illustration with pixel filter. Preserve ash-blonde bob hair, teal eyes, large brown witch hat with brass goggles, burgundy and brown alchemist coat, light cream shirt, small brown boots, friendly chibi proportions. Five equal cells in ONE horizontal row, full body every cell, ample transparent gutters, aligned boot bottoms. Left to right: neutral standing looking slightly left with small green flask held in left side of image; working pouring that flask toward left; cheerful success raising flask at left while other hand raised; surprised by experiment with hands near chest; sleeping seated with hat on, eyes closed. Same head size, same body scale, same costume across all five. Actual logical detail about 80 pixels wide by 112 pixels tall per standing sprite, enlarged by nearest-neighbor only: deliberate square pixel clusters, 1-pixel dark plum outline, 3-tone shading, restrained warm 32-color palette. No smooth shading, no anti-alias, no textures/noise, no white halo. Real TRANSPARENT RGBA outside sprites, no checkerboard painted in, no floor shadow, no labels/grid/cell borders. Each complete hat, hands, feet and raised flask entirely inside its own cell, large empty spacing between figures. Landscape sheet.
```

## cauldron.png

```text
Use case: stylized-concept. Asset type: single transparent game sprite. One small magical alchemy cauldron for a cozy 16-bit pixel-art RPG laboratory, front three-quarter view slightly from above. Round dark plum cast-iron pot, two small side handles, brass rim, subtle simple gold rune, short integrated furnace base with warm orange fire visible in a small window. Luminous teal liquid inside ellipse at top. NO steam, NO particles above pot, no scene, no floor shadow. True low-resolution pixel art at approximately 76 logical pixels wide and 62 high, enlarged with square crisp nearest-neighbor blocks. 1 logical pixel dark plum outline, 3-tone stepped shading, shared restrained warm colors: plum #332b3d, brown #674438, brass #c89958, cream #f0d9ab, jade #68b9a6, teal #3c858d. No smooth gradients, no soft edges, no texture noise, no white outline. Entire object centered with generous transparent padding, real TRANSPARENT RGBA background, no checkerboard pattern, no text. Clearly legible large pixel clusters, simpler than a detailed illustration.
```

## lectern.png

```text
Use case: stylized-concept. Asset type: one transparent RPG prop sprite. A compact wooden lectern with an open alchemy spellbook on its tilted top, sturdy single pedestal and small base. Three-quarter front view from slightly above, same perspective as a cozy laboratory game. AUTHENTIC coarse 16-bit pixel art: design at only 44 logical pixels wide by 64 high, enlarge as clean square pixel blocks. Readable big parchment pages with a few bold rune marks, brass corner accents, dark walnut pedestal. Restrained shared palette plum #332b3d, brown #674438 and #94664c, brass #c89958, cream #f0d9ab, jade #68b9a6. One logical pixel dark plum outline, 3-tone stepped shading. No tiny detailed engraving, no smooth shading, no anti-aliasing, no texture noise. Complete object with generous padding on real TRANSPARENT RGBA. No checkerboard pattern, no room, no floor, no cast shadow, no text outside book. This must look hand-placed pixel art, not a high-resolution illustration.
```

## basket.png

```text
Use case: stylized-concept. Asset type: one transparent game prop. Small EMPTY wicker ingredient basket, oval open top, two small loop handles, view from slightly above and front, cozy alchemy laboratory 16-bit RPG. Authentic coarse pixel art drawn at 48 logical pixels wide by 26 high, enlarged as sharp square blocks. Dark plum one-pixel outline, chunky readable wicker weave made from a few broad alternating pixels, dark interior. Only 3-tone stepped shading, shared palette dark plum #332b3d, walnut #674438, brown #94664c, tan #c89958, pale gold #e3c082. No tiny high-res weave, no gradients, no photographic texture/noise, no floor, no ground shadow, no contents. Real TRANSPARENT RGBA background, never checkerboard illustration. Entire basket and handles fully visible with ample padding. Same restrained clean pixel style as classic JRPG sprites.
```

## tray.png

```text
Use case: stylized-concept. Asset type: one transparent game prop. An EMPTY small rectangular wooden potion serving tray with low raised rim and simple brass corners, view from slightly above and front, cozy alchemy laboratory 16-bit RPG. Very shallow wide 3:1 shape, no legs. Authentic coarse pixel art drawn at 48 logical pixels wide by 16 high, enlarged as clean square blocks. Simple dark plum one-pixel outline and 3-tone stepped shading, large readable clusters. Shared palette dark plum #332b3d, walnut #674438, brown #94664c, tan #c89958, pale gold #e3c082. No decorative tiny detail, no photographic texture, no gradients, no soft lighting, no ground shadow, no floor, no bottle or other objects. Real TRANSPARENT RGBA background, no checkerboard illustration. Whole object fully visible with ample transparent padding. Must look like a small hand-pixelled inventory/world sprite, not a high-resolution illustration.
```

## work-pose.png

参照: character-sheet.png。単体出力はRGBで市松背景が焼き込まれたため、承認済みPython整形で外側に接続した明るい中性色だけを透過。顔・服・瓶の内部明部は消していない。全身の接地と寸法をシート由来4ポーズへ合わせる。

```text
Use case: identity-preserve. Reference is the five-pose sheet of the same alchemist girl. Create ONLY ONE revised WORK pose, isolated full body. Keep exactly the same pixel-art character identity, head size, costume, brown goggles hat, ash blonde hair, teal eyes, long burgundy coat, pants and boots, color palette and chibi proportions as the FIRST standing figure. She stands firmly with both boots on the same baseline. Extend her arm toward the LEFT of image, hold a small green flask tilted with its neck pointing DOWN-LEFT, ready to pour into a cauldron which is off image to the left. Other hand relaxed at her waist. NO second flask, no beaker in other hand, no stream yet, no cauldron. Keep all hat, flask and boots inside image. Authentic crisp 16-bit pixel art, 1 logical pixel dark outline, no soft edges or gradient. Approximately 85x110 logical pixels of character detail enlarged as square pixels. Real TRANSPARENT RGBA with generous padding, no checkerboard pattern, no floor, no shadow, no labels.
```

採用結果は首を大きく傾けた注ぎ姿勢ではなく、釜側へ手を伸ばした姿勢。アプリでは手元から釜の口へ小さな素材の粒を移動させる。
