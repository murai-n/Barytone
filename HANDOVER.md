# 引き継ぎ

更新 2026-11-15。PR #1〜#5 はマージ済み。
全体像・設計・検証結果は `README.md`。このファイルは**残っている作業と未解決の問題**だけを書く。

## 前提と制約

- **リポジトリは非公開のまま**。`datasheets/` にメーカー公開の PDF が入っている。
- **Phase One のファイル（`.fcrv` など）は解析のみ、ローカルで行う。** Barytone に置くのは
  そこから導出した補正値だけ。ベンダーファイルそのものはコミットも再配布もしない。
  成果を書くときは「Capture One のカーブを解析した」ではなく、何をどう測って何が得られたかを
  事実として書く。
- スクリプト内のパスは `/home/claude/...` 固定。別の場所で動かすときは
  `/home/claude/{scripts,ds,m3,out3,paper,bake3}` をリポジトリへのリンクにする。
- カラー側の `model.py` はリポジトリに入っていない `work/` を読む。モノクロは `spec3.py` で完結。
- キットの再パッケージに**特定カメラのプロファイルは不要**（`kit/` を固めるだけ）。

## 解決：Nikon で約 1.5 EV アンダーになる（2026-11-15）

Capture One 23 の Film Curves（`.fcrv`、約 3700 ファイル）を解析して原因が分かった。

- Capture One は RAW の中間グレーを低めに置き、既定のカーブ **Film Standard** で持ち上げて
  ふつうの明るさに見せている。キットは **Linear Response** を使うので、その持ち上げが消える。
- 補正量は機種ごとに `.fcrv` から計算できる（`scripts/camera_ev.py` → `ds/camera_ev.json`、570 機種）。
  グレーカードが Film Standard で 0.18 になる RAW 値 x を求め、Linear Response でのその明るさとの比を取る：
  `x : FS(gain_FS·x) = 0.18`、`offset = log2(0.18 / LR(gain_LR·x))`。
  Nikon Z5 / D750 +1.25、D810 +1.26、Z6・Z7・Z8 +1.45、Canon R5・R6 +1.34、Fuji X-T4・X-T5 +1.57、Leica Q2 +0.27。
  全機種の中央値 +1.27、範囲 +0.07〜+1.86。**メーカー単位の既定値は採れない**（Nikon 内でも +0.18〜+1.59）。
- カーブの座標はリニア光と解釈している。ガンマ 1.8 と読むと Z5 は +2.57 になり、実測の約 1.5 と合わない。
  リニアでも実測と 0.25 EV ずれるので、**グレーカードでの確認が 1 枚ほしい**。
- `gain` 欄は Fuji・Phase One 等の Film Standard だけ 1.418（= +0.5 EV）で、Linear Response は 1.0。
  カーブ前に掛かる露光倍率と解釈して計算に含めている。

**実装済み**: 焼き込みツールは、選んだカメラの値を表から自動で入れ（手で変更可）、生成する
全 Film スタイルに `Exposure` として書く。値はマイカメラにも記憶。表にない機種は中央値で、画面にそう出る。
`.fcrv` そのものはリポジトリに入れていない（数値だけ）。

`.fcrv` の形式（版 6）: `II`/`MM`、u32 版、カーブ A、u32 フラグ、文字列 2 本（u32 長さ + 本文）、
u32 種別、f32 ゲイン、u32 × 3、カーブ B、カーブ C。カーブは u32 点数 + 点 ×（u32 x, u32 y）で、
x・y は 2^32−1 を 1 とする固定小数。版 2・4・5（旧機種、134 ファイル）は未対応。

## 解決：「肩が二重に掛かっている」は大半の機種で起きていない

**Linear Response は 580 機種中 549 機種で完全な直線**（3 本のカーブとも (0,0)→(1,1)、ゲイン 1.0。
Nikon Z5 を含む）。フィルム特性曲線の肩と Capture One の肩が二重に掛かることはなく、
Linear Response の逆関数を Develop カーブに畳み込む作業は不要。
例外は 31 機種（Leica Q・SL・X 系の 11 点カーブ、Mamiya M18/M22/M31 のゲイン 1.418、Epson R-D1 など）。
これらは露光オフセットの計算には Linear Response のカーブを含めてある。階調の形まで直すかは未決。

## ICC の置き場所：OS で逆（2026-11-15、Mac で確認）

スタイルから ICC を当てられるかは、置き場所で決まる。

| OS | `/Library/ColorSync/Profiles`（Mac）・既定の Color Profiles（Windows） | Styles フォルダ |
|---|---|---|
| Mac | 当たる（確認済み） | 当たらない（確認済み） |
| Windows | 当たらない（以前の報告） | 当たる（以前の報告） |

Mac で Styles フォルダに置くと、「スタイル "Film KVPS (Nikon Z5)" には、バリアントに適用できない ICC
プロファイルが含まれています。ICC プロファイルが壊れている可能性があります。」と出る（カーブの
Linear Response は当たる）。ICC の中身は原因ではない。同じファイルを ColorSync に置けば当たるし、
下の 2 つのタグを取り除いた版でも Styles フォルダでは当たらなかった。

- 以前合意した「両 OS とも ICC フォルダを Styles に入れて統一」は、**Mac では使えない**ので取りやめ。
  Mac は今のツールとマニュアルの案内（`/Library/ColorSync/Profiles`）のままでよい。
- Windows は以前の報告どおりなら Styles フォルダが正しく、ツールの案内（Color Profiles）を変える必要がある。
  手元で未確認なので、Windows で 1 回確かめてから直す。

参考：Capture One 23 の「Nikon - Neutral」などの Look 系プロファイルは Nikon 共通で、Z5 用のファイルにも
内部名「NikonD850-Nikon - Neutral」と、組にするカーブの指定（`P1FC` タグ = `NikonC1-Look Neutral`）が入っている。
焼いた ICC にも残るが、ColorSync に置けば問題なく当たる。

## 次の着手順

1. Nikon Z5 でグレーカードを撮り、表の +1.25 EV で L\* ≈ 50（sRGB ≈ 119）になるか確認
   （ずれたら、カーブ座標の解釈か gain の扱いを見直す）
2. Windows での ICC の置き場所を確かめ、ツールとマニュアルの Windows 向け案内を直すか決める（下記）
3. Linear Response が直線でない 31 機種の階調をどうするか
4. キット再パッケージ

## テストの走らせ方

```
python3 bake3/make_fixture.py /tmp/co_test       # 試験用カメラプロファイル 12 個
python3 bake3/build.py                            # /home/claude/bake/dads にデザインシステムが要る
CO_TEST=/tmp/co_test node bake3/t_browser.js      # 84 件
```

デザインシステムは `digital-go-jp/design-system-example-components-html` を
`/home/claude/bake/dads/html` に clone し、`npm pack @digital-go-jp/design-tokens` を
展開した `package/` を `/home/claude/bake/dads/pkg/package` に置く。

モノクロ側の検証は `README.md`「モノクロ ICC の作り方と検証」。
モノクロのグレー位置（速度点 +1.1 log）は `mono.METER_LOG` の1か所にあり、`export_mono.py` が
`films.json` 経由でブラウザのエンジンに渡す。`mono.py` を変えたら `export_mono.py` →
`node bake3/src/test_mono.js`（JS と Python の一致）→ `build.py` の順で回すこと。
