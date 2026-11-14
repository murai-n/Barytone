# Barytone

Capture One 用のフィルム再現キット。プリセット集ではなく、**各メーカーが公開している
データシートから撮影・現像・プリントの工程そのものを計算**している。

名前は印画紙のバライタ層から。語源はギリシャ語の *barys*（重い）で、同じ根を持つ
*barytone*（＝重い調子、baritone の異綴り）に綴りごと重ねてある。このキットが最後に
目指すのが紙の Dmax、つまり深く重い黒であること、そして扱っている量がどこまでいっても
tone（paper tone、slide tone、温黒調・冷黒調）であることの両方にかかっている。

---

## 構成

ICC プロファイルがフィルムの色の個性を担い、Capture One のスタイル（.costyle）が
現像とプリントを担う。ICC と Film スタイルは配布物に含めず、同梱の焼き込みツール
（HTML、ブラウザ内で完結）が利用者の端末で生成する。

    撮影 → ICC（フィルムの色）→ Coupler → Paper（印画紙）→ 観察条件

スタイルフォルダは重ね順どおりに並ぶよう接頭辞を付けてある（1 Film → 2 Coupler →
3 Paper → 4 Filter）。

## いまの状態

### カラー：完成・配布済み（30 本）

Pro Image 100、Portra（現行3本＋旧世代 NC/VC 4本）、Ektar 100、Gold 200、
Ultra Color 100UC/400UC、Vericolor III、Vision3 500T、Fuji Pro 160NS/400H/800Z、
Superia X-TRA 400、Provia 100F、Velvia 50/100、Astia 100F、Ektachrome E100/EPN、
Kodachrome 25/64/200、Ektachrome 64T/160T、Fujichrome 64T Type II。

印画紙は 8 種（Endura、Crystal Archive ほか）＋近似 Ilfochrome。

### モノクロ：完成

- フィルム 9 本（分光感度＋特性曲線）→ `ds/mono_films.json`
- 印画紙 4 種（代表カーブ＋号数別 ISO Range / Speed）→ `ds/mono_papers.json`
- レンダリング経路 → `scripts/mono.py`（検証済み）
- **ICC 45 本（フィルム 9 × フィルター 5）→ 焼き込みエンジンに組み込み済み**。
  `scripts/export_mono.py` が `films.json` にモノクロのデータを追加し、`engine.js` の
  `monoRender()` が焼く。JS と Python の差は XYZ で 2e-10。LittleCMS を通した検証
  （`scripts/check_mono_icc.py`）で 45 本とも無彩色・階調単調・中間グレー L\* 50 を確認。

残作業はこの順：

1. ~~**ICC 生成**~~ — 完了（下の「ICC と印画紙スタイルの分担」）。
2. ~~**スタイル生成**~~ — 完了。`scripts/styles_mono.py` が印画紙 4 種 × 号数 00〜5 の 28 本を
   `3 Paper (B&W)` に書く（`presets.py` の最後から呼ぶ）。名前は `Paper IMR grade 2` の形で、
   IMR = MGIV RC、ICT = RC Cooltone、IMF = MGIV FB、IFW = FB Warmtone。
   ICC ＋スタイルと `mono.render()` の差は 9 フィルム × 300 色で最大 ΔE76 0.49。
   プリント露光は中間グレー L\* 50 基準（下の「プリント露光の基準」）。
3. **ツール再ビルド** — ビルドとブラウザテストまで完了（52 件すべて合格）。焼くのは 75 本
   （カラー 30 ＋ モノクロ 45）。モノクロの見本は MGIV RC 2 号で焼いた状態を表示し、使い方の欄に
   印画紙スタイルを重ねる手順を足した。アーティファクトは再公開済み（Version 35）。
   テストの実行：

       python3 bake3/make_fixture.py /tmp/co_test       # 試験用カメラプロファイル 12 個
       python3 bake3/build.py                            # /home/claude/bake/dads にデザインシステムが要る
       CO_TEST=/tmp/co_test node bake3/t_browser.js

   デザインシステムは `digital-go-jp/design-system-example-components-html` を
   `/home/claude/bake/dads/html` に clone し、`npm pack @digital-go-jp/design-tokens`
   を展開した `package/` を `/home/claude/bake/dads/pkg/package` に置く。
4. ~~**ドキュメント更新**~~ — 完了。技術資料に「モノクロ」の章を追加し、「データの代用・借用」に
   モノクロ 5 項目（T-Max 400、FB Warmtone、フィルター、温黒・冷黒、曲線の整形）を追記。
   マニュアルにも「モノクロで使う」の章、作られるものの本数（75 本）、`3 Paper (B&W)` フォルダ、
   モノクロの収録銘柄を追加。
5. ~~**キット再パッケージ**~~ — 完了。`kit/`（`add-built-kit` ブランチから取り込み）の
   焼き込みツールを新しいビルドに替え、`kit/3 Paper (B&W)` に 28 本、マニュアル PDF を
   更新後の版に差し替えた。キットはカメラに依存しないので、`work/` も特定カメラの
   プロファイルも要らない（`python3 scripts/styles_mono.py kit` で B&W だけ作り直せる）。

---

## モノクロの設計

### フィルターを ICC に焼き込む理由

モノクロ ICC は入力 RGB を無彩色に畳む。Capture One のレイヤーは ICC の後段なので、
受け取る時点で色情報が消えており、黄フィルターの「青を落として赤を残す」が効かない。
実物のフィルターはフィルムの分光感度が積分する**前**のスペクトルを変えるので、
ICC の中が物理的に正しい位置になる。

    H = ∫ S(λ) · T_filter(λ) · sens(λ) dλ

レイヤー方式にすると、フィルターは RGB 3 チャンネルへの係数に退化する
（分離可能になる代わりに、濃赤と淡赤の差やメタメリックな被写体の挙動が出せない）。
検討のうえ ICC 方式を採用した。

### 連鎖

シーン → フィルター → フィルムの分光感度で単一チャンネルへ → 特性曲線 → ネガ濃度
→ 印画紙（号数別カーブ）→ 反射率 → 無彩色 XYZ（紙の調子ぶんだけ色が乗る）

### 実装上の要点

- **ネガの濃度域は、号数の ISO レンジ中央に合わせる。** これを外すとハイライトが
  紙のレンジ外に出て飛ぶ。暗室での号数選択と同じ原理。
- **特性曲線と印画紙カーブは `clean_curve()` で整えてから使う。** 等間隔の log 露光
  グリッド（0.005）に載せ、単調回帰（PAVA）、σ 0.03 のガウスで平滑化する。以前は
  累積最大を取っていたが、トレースの揺れやラスタの段差がそのまま平坦部になり、
  MGIV RC では濃度 0.8 付近（中間調）に一段のグレーの帯が出ていた。元トレースとの
  差は 95% 点でフィルム 0.006、印画紙 0.06 以内。
- フィルム速度の基準は、データシートの軸ではなく**フィルム自身の速度点**
  （ベース濃度 +0.10）で取る。Ilford は相対 log 露光、Kodak は絶対で軸が揃わないため。

### 検証済みの挙動

号数ごとの硬さ（HP5 Plus、中間グレーでのプリントの傾き γ）: MGIV RC 00 号 0.64 → 2 号 1.06 →
5 号 3.06、RC Cooltone 0.86 → 1.56 → 3.14、MGIV FB 0.68 → 1.17 → 3.06、FB Warmtone 0.68 → 1.06 → 2.40。

号数スイープ（Pan F Plus / MGIV RC、sRGB の黒〜白ランプ）: 00 号 43→234 の軟調、
2 号 31→245、5 号 29→247 の硬調。9 フィルム × 4 紙 × 7 号数のすべてで、グレーランプは
端の飽和を除いて単調増加。

フィルター（HP5 Plus / MGIV RC 2 号、sRGB 値。被写体は空 86,140,200、赤レンガ 160,70,50、
葉 70,110,50）:

| | 空 | 赤レンガ | 葉 |
|---|---|---|---|
| なし | 177 | 94 | 84 |
| 黄 | 148 | 107 | 97 |
| 橙 | 119 | 126 | 92 |
| 赤 | 115 | 163 | 75 |
| 緑 | 151 | 84 | 104 |

赤で空が最も暗く・レンガが最も明るい、緑で葉が最も明るい。教科書どおり。

### プリント露光の基準：中間グレーを L\* 50 に

`mono._mid_offset()` は、測光した中間グレーが表面反射込みで L\* 50 に刷られる露光を、
紙と号数ごとに印画紙カーブから求める（テストストリップで決めるのと同じ考え方）。
以前は「ネガの濃度域を号数の ISO レンジ中央に合わせる」方式だったが、グレーカードが
L\* 28〜37（約 1 段暗い）で刷られ、軟調の号数では白が濁っていた。

HP5 Plus、L\*（グレー／白 90%／白／白 +1 段）:

| | 以前 | いま |
|---|---|---|
| MGIV RC 00 号 | 37 / 69 / 71 / 87 | 50 / 84 / 86 / 94 |
| MGIV RC 2 号 | 37 / 91 / 92 / 94 | 50 / 95 / 96 / 97 |
| MGIV FB 2 号 | 33 / 90 / 93 / 96 | 50 / 96 / 96 / 97 |

2 号までは白が紙の白（MGIV RC 97.2）の手前に残る（「いま」の列は曲線の外れ点を除いた後の値）。4〜5 号では白 90% が紙の白に届く
（硬調で中間グレーを合わせればハイライトは飛ぶ。暗室でも同じ）。

### ICC と印画紙スタイルの分担

暗室と同じところで切る。**ICC がネガ（フィルム＋フィルター）、スタイルがプリント
（印画紙＋号数）**。こうすると印画紙スタイルはどのフィルムにも使える。

ICC は、中間グレーを基準にしたネガ濃度 u（＋が薄い＝シャドウ）を、Capture One の
カーブが扱う値（リニア光の 1/1.8 乗、`styles.py` の `ENC`）に一次式で書き込む。

    v = 0.18^(1/1.8) − u / 2.4        （ICC が出す無彩色 Y = v^1.8）

- 中間グレーは L\* 50 のまま動かない。
- 濃度 2.4 ぶんがカーブの 0〜1 に収まる。9 本のネガの全濃度域（u = −1.32〜+0.79）が
  v ≈ 0.06〜0.94 に入り、どちらの端も切れない。
- そのため ICC 単体の見た目は、白が 167 前後に沈んだ平坦なネガスキャンになる。
  階調は印画紙スタイルでつける。
- 印画紙スタイルのカーブは `mono.print_from_value(v, paper, grade)` そのもの。
  ICC → このカーブの合成は `mono.render()` と 1e-14 で一致する（33 格子の ICC を
  LittleCMS で通すと、ICC の値で最大 0.003、プリントで最大 2.7 階調の差）。
- カーブの傾きは中間グレーで 2 号 1.9、5 号 5.1、最大では 5 号で 10.6 になる。16 点のカーブでは硬い号数を
  描ききれないので、手順 2 では制御点を増やすこと。

ファイル名はカラーと同じ形で `<カメラ>-Film <ID> <フィルター>.icm`。ID は IHP5・IFP4・
ID100・ID400・IPANF・ISFX200・KTM100・KTM400・KTX400、フィルターは base（なし）・
Y・O・R・G。

---

## データ代用（ドキュメントに明記すること）

- **T-Max 400** — 分光感度が非掲載のため T-Max 100 から借用（同じ T-GRAIN 系）
- **MGIV FB・FB Warmtone の曲線の形** — MGIV FB のデータシートは単独の曲線の図が PDF 上で
  欠けており（縦線しか残らない）、トレースは 00〜5 号を重ねた図から各号の曲線をつぎはぎした
  形になっていた（00 号でも硬く、シャドウが沈まない）。両紙とも MGIV RC の形（同じ
  Multigrade IV 乳剤）を借り、号数別の ISO Range は自身の値を使う（`mono.SHAPE_FROM`）
- **RC Cooltone のトレース** — 単独曲線の図の立ち上がりに注記の文字があり、トレースが
  それを拾って濃度 0.15 の平らな段になっていた。段が ISO レンジの一部を食い、全号数が
  極端に硬くなっていた（00 号で中間グレーの傾き 2.8）。注記と枠の区間を除外（`mono.STRAY_X`）
- **FP4 Plus の肩の先** — 肩（D 1.87、x 4.14）より先で、トレースが濃度目盛りの「2.0」の
  横線を拾い、グレー +6.4 段で D 2.0 へ跳ねていた。その区間を除外（`mono.FILM_STRAY_X`）。
  Ilford の 6 本はどれも 1 条件 1 本の図で、号数違い・現像時間違いのつぎはぎはないことを
  データシートの図と重ねて確認済み
- **トレースの外れ点** — 曲線から 0.02 以上外れた点（注記・枠）は、許容差つきの最長単調列を
  残して落とす（`mono._longest_rising`）。MGIV RC の肩の「×」印もこれで消える
- **コントラストフィルター** — 実測透過率が入手できないため、公称カットオンに基づく理想化モデル
- **紙の色（ベースと画像の色）** — Ilford は文章でしか示していない（Warmtone「warm black image
  tone on a warm white base」、Cooltone「cool-of-neutral image tone on a cool white base」、
  MGIV RC「bright base tint」「cool-to-neutral」）。紙の白にベースの色、銀の濃いところに画像の色を
  CIELAB の a\*, b\* で与え、その間を銀の吸収（1 − 10^−(D − Dmin)）で混ぜる。値は文言に合わせた
  代用値（`mono.TONE`）：Warmtone ベース b\* +4・黒 +7、Cooltone ベース −2.5・黒 −4、
  MGIV RC ベース −1.5・黒 −1、MGIV FB ベース +0.8・黒 0
- **Ektachrome EPN → E100 の色素**、**Velvia 100 → Velvia 50 の色素**を借用
- **Ilfochrome** — プリント紙の特性曲線が非公開のため全体を近似

### モノクロの原理的な限界

カメラは CFA を通った後の RGB しか持たないため、フィルムの分光感度は 3 チャンネルの
線形結合で近似される。SFX 200 の真の赤外効果（Wood 効果）はセンサーが記録していないので
再現できない。可視域の「赤を明るく／青を暗く」までが範囲。

---

## ディレクトリ

| パス | 中身 |
|---|---|
| `scripts/` | モデルと生成パイプライン（`model3.py`、`styles.py`、`presets.py`、`export4.py`、`build3.py`、`mono.py`、`spec3.py`、`export_mono.py`、`check_mono_icc.py`、`test_profile.py`、`styles_mono.py`） |
| `ds/` | digitize 済みデータと抽出スクリプト |
| `m3/` | 色素・分光の基礎データ |
| `paper/` | 印画紙データ |
| `bake3/` | 焼き込みツール（`src/engine.js` が計算本体、`build.py` でビルド、`t_browser.js` がテスト） |
| `datasheets/` | 出典の PDF（メーカー公開資料。リポジトリは非公開のまま運用すること） |

### モノクロ ICC の作り方と検証

カラー側の `model.py` は、リポジトリに入っていない `work/` のデータを読む。モノクロは
`spec3.py`（`model3.py` から分光の部分だけを抜いたもの）で動くので、これだけで完結する。
スクリプトの中のパスは `/home/claude/...` 固定なので、別の場所で動かすときは
`/home/claude/{scripts,ds,m3,out3,paper,bake3}` をリポジトリへのリンクにしておく。

    pip install colour-science scipy pillow
    python3 scripts/export_mono.py                  # films.json にモノクロを追加、m3/ref_mono.json を更新
    node bake3/src/test_mono.js                     # JS エンジンと mono.py の一致
    python3 scripts/test_profile.py /tmp/TestCam-Generic_Neutral.icm   # 試験用のカメラプロファイル
    node bake3/bake_mono.js /tmp/TestCam-Generic_Neutral.icm /tmp/icc  # 45 本を焼く
    python3 scripts/check_mono_icc.py /tmp/TestCam-Generic_Neutral.icm /tmp/icc

`test_profile.py` は sRGB → Lab の mft2 プロファイル（33 格子）を作る。実物のカメラ
プロファイルの代わりで、焼き込みと LittleCMS での読み戻しを試すためのもの。
LittleCMS は Lab 系の入力プロファイルで機器の白を紙の白に寄せる補正をかけるので、
検証ではこれを切っている（`cmsFLAGS_NOWHITEONWHITEFIXUP`）。

### データ抽出のしかた

データシートによって描かれ方が違うので、2 系統ある。

- **ベクター PDF**（Kodak、Fuji の一部）→ `ds/extract4.py`。pdfplumber でパスを直接読む。
  曲線が断片で描かれる場合や、直線部が `lines` として出る場合に対応済み。
- **ラスタ PDF**（Ilford は曲線も目盛りも画像）→ `ds/trace.py`。枠と目盛りを自動検出して
  軸を較正し、列ごとにインクを追う。`mode` は `longest`（既定）/ `lowest`（2 本重なりの下側）/
  `continuous`（seed から左右へ追跡）。`grid=True` で内部グリッド線を除去。
  後処理に `despike()` と `monotonic_trim()`。

## 外部参照

- 焼き込みツールのアーティファクト: `c0266795-bc1c-42f1-874a-81c2742f4c69`
- マニュアル: doc `c447f219-b1d8-4df4-96a2-dd2618626da9`（node `80327a72-01e4`）
- 技術資料: doc `8661681c-19fb-485e-9843-993af9b4d0bc`（node `1eb4c6dd-23e5`）

---

## `kit/` — 配布物の実体

`kit/` に、配布 ZIP の中身がそのまま入っている（ビルド済み）。再パッケージはこのフォルダを
固めるだけで済む。

| 中身 | 数 |
|---|---|
| `焼き込みツール.html` | 1（ブラウザ内で ICC と Film スタイルを生成する） |
| `Film Process Kit マニュアル.pdf` | 1 |
| `2 Coupler/` | 4 |
| `3 Paper/` | 16（印画紙 8 種 × normal / faded） |
| `4 Filter/` | 6 |

スタイルはいずれもカメラに依存しない。**カメラプロファイルは配布物に含めない**：利用者が
焼き込みツールで自分の Capture One プロファイルを選び、ブラウザ内で ICC を生成する。
したがってキットを作る側に特定カメラのプロファイルは不要。

モノクロ（`3 Paper (B&W)` など）はまだ存在しない。ICC・スタイル生成が未着手のため。
