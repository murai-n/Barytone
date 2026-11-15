# 引き継ぎ

更新 2026-11-15。main = `aba7846`（PR #1・#3・#4 すべてマージ済み、未マージ差分なし）。
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

## 未解決：Nikon で約 1.5 EV アンダーになる

適用時点で大きくアンダーに振れる。原因は 3 つに分解できた。

1. **Linear Response が Capture One のトーンカーブを外す** — 支配的。カメラ非依存。
2. **Nikon の RAW ヘッドルーム** — 機種ごとに違う。
3. **モデルが中間グレー = 0.18 を仮定している** — 設計どおりなので触らない。

補正の置き場所は **Film Develop スタイルの既定露光**。`ref` や ICC には入れない
（`ref` は測光基準、ICC は色の個性で、どちらもカメラ非依存であるべき）。

メーカー単位の既定値は**採れない**。実測 ISO はブランド内でばらける
（公称 12800 に対し Nikon D7200 8998 / D750 9443 / D810 9631）。機種単位の話であって
ブランド単位ではない。

### 合意済み・未実装

- 焼き込みツールに**編集可能な露光オフセット欄**を追加。既定 **+1.5**、生成する全 Film
  スタイルに適用。グレーカードでの合わせ方を手順として書く（目標 L\* ≈ 50、sRGB ≈ 119）。
- ICC の置き場所を統一：`ICC (カメラ名)` を**フォルダごと** Styles フォルダに入れる方式に、
  ツールとマニュアルの両方を揃える。Windows では既定の場所に置くと style から適用できず、
  Styles フォルダに置くと通る。mac でも配置がまとまるので同じ方式にする。

## 未解決：肩が二重に掛かっている

```
Linear Response の肩 → フィルム特性曲線の肩 → 印画紙の肩
     (C1 由来・不要)       (データシート由来)      (意図どおり)
```

Linear Response は直線ではない。Capture One は機種ごとに `.fcrv`（Film Curve）を持ち、
Linear Response はそのうち最も平坦な 1 本に差し替えるだけで、ハイライトのロールオフは残る。
中間部もわずかに持ち上げ／寝かせが入る（機種差あり）。

結果、各銘柄の肩の個性（Velvia の硬い潰れ方と Portra のなだらかな伸び方の差）が鈍る。
露光オフセットでは明るさが合うだけで、階調の形は戻らない。

物理的に正しいベースは Linear Scientific だが、**ほとんどの機種で選択肢に出ない**
（Phase One 自社バックが主）。確認済み。

### 方針

`.fcrv` を読んで **Linear Response の逆関数をキットが書き出す Develop カーブに畳み込む**。

- `.fcrv` は機種固有なので、利用者のカメラに正確に合う
- Base Characteristics は Linear Response のまま（選べる中で最平坦）
- Barytone に置くのは導出した補正値だけ

ユーザーが Capture One の **Film Curves フォルダ**を送る予定。届いたら形式を確認し、
補正値の抽出まで進める。Windows では
`C:\Program Files\Phase One\Capture One <n>\Film Curves` にある。

## 次の着手順

1. Film Curves フォルダが届いたら `.fcrv` の形式を読む → 補正値の抽出
2. 露光オフセット欄（既定 +1.5）をツールに追加、生成スタイルに適用、マニュアルに手順
3. ICC 配置をフォルダ単位に統一（ツール＋マニュアル）
4. キット再パッケージ

## テストの走らせ方

```
python3 bake3/make_fixture.py /tmp/co_test       # 試験用カメラプロファイル 12 個
python3 bake3/build.py                            # /home/claude/bake/dads にデザインシステムが要る
CO_TEST=/tmp/co_test node bake3/t_browser.js      # 75 件
```

デザインシステムは `digital-go-jp/design-system-example-components-html` を
`/home/claude/bake/dads/html` に clone し、`npm pack @digital-go-jp/design-tokens` を
展開した `package/` を `/home/claude/bake/dads/pkg/package` に置く。

モノクロ側の検証は `README.md`「モノクロ ICC の作り方と検証」。
モノクロのグレー位置（速度点 +1.1 log）は `mono.METER_LOG` の1か所にあり、`export_mono.py` が
`films.json` 経由でブラウザのエンジンに渡す。`mono.py` を変えたら `export_mono.py` →
`node bake3/src/test_mono.js`（JS と Python の一致）→ `build.py` の順で回すこと。
