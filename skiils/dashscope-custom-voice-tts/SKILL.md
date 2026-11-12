---
name: dashscope-custom-voice-tts
description: 用本地 Qwen3-TTS、阿里云百炼自定义音色或 Breeze 音色合成语音。内置音色表（PFA 本人 / 纳西妲 / PFA 云端），本人默认用 10.31 s 参考音频做离线零样本克隆，本人与纳西妲音色已锁定指纹，用户点名某个音色时按表解析后合成，适用于配音、试音、批量旁白，以及把某个音色落成音频资产。
---

# 自定义声音合成

## 最终定案（2026-11-06，已锁定）

用户试听同一文案的两条对比成品后确认：**本地就用 `pfa` 这个声音**，参考音频是 10.31 s 的 `voices/pfa.wav`（SHA `90545ea6…`，原 `pfa-specified.wav`，由 8.7 s 云端净化参考克隆出的长句成品）。同日他把 2026-11-04 那批对照素材的 wav 全部删掉，**不留回退项**。

硬规则，不要再动：

- “我的声音 / 本地 / 本人 / 彭凡遨 / 彭发豪（音近异写）”一律 `--voice pfa --offline`；只有明确说“百炼 / 云端”才用 `pfa-cloud`。
- **不要替换 `voices/pfa.wav` 的内容**。`pfa-mic` / `pfa-clean8` / `pfa-clean12` / `pfa-orig-long` / `pfa-specified` 这些条目和文件都已撤销删除，磁盘上不存在，别再按历史名字引用它们。
- 当前默认参考是模型生成物当参考（会带一层模型音色痕迹），这是用户知情后的选择。**不要自作主张换回真人麦克风原声**——那份 18.12 s 素材在本技能目录里已无副本，只剩 `~/Library/Application Support/DouyinWelcome/voice/26FA14DC-AEB0-4D99-9C04-6AE3D1F77A65.wav`，要改必须先问用户。
- **纳西妲完全独立，改动本人音色时不要碰它。**
- `manifest.json` 顶层 `default_voice` / `locked`，条目里的 `ref_sha256` 把 `pfa` 和 `nahida` 锁住。`synthesize_local.py` 用音色表参考时会自动校验指纹，文件被换过就报错；`--reference-audio` 显式覆盖是允许的（临时试素材）。
- 真要有意换默认参考：先改 `manifest.json` 的 `ref_sha256`、`locked`、`default_voice` 和 `ref_text`，再换 wav，**不要只覆盖文件**。

```bash
python scripts/voices.py --default     # 打印锁定的默认音色
python scripts/voices.py --verify      # 核对全部参考音频指纹，被换过退出码 1
```

## 先解析音色，再动手

用户说“用我的声音”“用纳西妲的声音”“换成 PFA”“还是那个人声”时，**第一步不是拼参数，而是查音色表**：

```bash
python scripts/voices.py --list          # 列出全部已登记音色
python scripts/voices.py --default       # 打印锁定的默认音色
python scripts/voices.py 我的声音         # 别名、拼音、碎片句都能命中
```

命中的条目里有 `engine` 字段，它决定走下面哪一节：`local` = 本地千问3 克隆，`bailian` = 百炼自定义音色。不要凭记忆猜 voice id 或参考音频路径，也不要为已登记的音色重复上传参考录音。**“我的声音 / PFA”默认是本地离线克隆，参考音频是 2026-11-06 定案的 10.31 s `voices/pfa.wav`**；只有用户明确说“百炼 / 云端 / DashScope”才用 `pfa-cloud`，绝不因为本地慢就悄悄改走云端。**纳西妲是独立音色，改动本人音色时不要碰它。**

| 音色 | 引擎 | 参数 | 说明 |
| --- | --- | --- | --- |
| `pfa` PFA 本人 | 本地千问3 克隆 | `voices/pfa.wav`（10.31 s / 24 kHz / 单声道，峰值 0.95）+ 该成品原文逐字稿 | **默认本人音色，已锁定**；2026-11-06 用户试听对比后选定，“我的声音”“本人”“彭凡遨”“默认音色”都命中它 |
| `nahida` 纳西妲 | 本地千问3 克隆 | `voices/nahida.wav`（14.56 s / 24 kHz / 单声道）+ 逐字稿 | 第三方游戏角色音色，私人试听/自用；公开直播或发布需授权并标注 AI 合成；**已锁定，始终保持原样** |
| `pfa-cloud` PFA 云端 | 百炼自定义音色 | voice ID + `qwen-audio-3.1-tts-flash` | 原先的默认云端音色，按量计费 |

用户没点名音色时，沿用上一次用过的那个（同一段对话里通常已经解析过），并把选择说清楚：“这段用你本人的本地克隆音色”。

## 新增音色

加角色只需一步，脚本会把片段统一成 24 kHz 单声道并写进音色表：

```bash
python scripts/prepare_voice.py \
  --name furina --label 芙宁娜 \
  --from ~/path/长素材.wav --start 42 --duration 12 \
  --text "这段音频里逐字说的话" \
  --aliases 芙宁娜,水神,芙卡洛斯 \
  --authorization "第三方角色音色，公开使用需授权并标注 AI 合成"
```

片段取 **6–15 秒干净单人声**（有背景音乐、笑声、多人抢话都会拖垮克隆）。`--text` 必须与片段**逐字一致**；留空也能跑（靠说话人编码器提音色），但节奏更飘。参数、路径、授权说明都记在 `voices/manifest.json`，不要写在脚本里。

## 本地 Qwen3-TTS

Apple Silicon Mac 上的 MLX Audio，完全离线，参考音频不出本机。需要 `mlx-audio`、`numpy`、`soundfile`，本机独立解释器在 `~/tools/qwen-tts/.venv/bin/python`；脚本发现当前解释器没有 `mlx_audio` 会自己 exec 到它（可用 `QWEN_TTS_PYTHON` 改），所以直接 `python3` 调也行。

```bash
# 本人音色
python scripts/synthesize_local.py \
  --voice pfa --offline \
  --text "你好呀，今天也要记得好好照顾自己哦。" \
  --output /absolute/path/pfa.wav

# 换成纳西妲
python scripts/synthesize_local.py \
  --voice nahida --offline \
  --text "须弥的雨季到了，记得带伞呀。" \
  --output /absolute/path/nahida.wav
```

- `--voice` 走音色表；临时换素材可以给 `--reference-audio`（会覆盖音色表里的参考音频），这时记得同时给与音频逐字一致的 `--reference-text`，否则沿用音色表的逐字稿会读错。
- `--offline` 强制只用本地权重；模型已缓存在 `~/.cache/huggingface`，再没有就明确告诉用户要先联网取一次。
- 默认模型 `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit`，`--model` 可换完整本地路径。
- 实测（本人 10.31 s 参考，2026-11-06）：15 字短句 3.42 s / rms 0.109 / 峰值 0.876，34 字文案 6.77 s / rms 0.132 / 峰值被自动从 0.955 压到 0.95，均未跑飞；参考短于 15 s，不再出现超长警告。同日对照：14.75 s 真人麦克风参考出 5.20 s / rms 0.036（比本参考轻约 13 dB、底噪窗高 4 倍、语速快 1.57 s），用户听完仍选定 10.31 s 这条。批量旁白按**自然句段**分段合成，逐段听误读，再按真实音频时长排时间线。
- 脚本自带三道护栏：参考音频超过 15 s 会警告；输出时长超过文案估算值时会报「跑飞告警」并返回码 2（别把那段当成品）；输出峰值超过 0.95 自动压到 0.95，避免削波。
- 这是 0.6B / 4-bit 的零样本克隆，长句的中后段容易吐字含糊或漏字。遇到这种情况先拆句，别急着换模型或换参考；也别把云端结果当成「本地模型应有的水平」。
- 不要声称克隆结果与本人完全一致；交付前核对音色、语速、多音字、音量和首尾静音。

## 净化参考：云端出干净素材，本地再克隆

麦克风参考录音若削波、带底噪、时长偏长，本地 0.6B 模型会明显掉质量。做法：用**用户已授权的云端本人音色**合成一段无背景噪声、标点干净、无英文/数字混排的文案，把它转 24 kHz 单声道当新的参考音频；逐字稿就是那段文案本身，天然对齐。把本地克隆出来的成品再当参考也走这条链路——**代价是音色会带上模型痕迹**；2026-11-06 用户正是在知情后选定了这样一条 10.31 s 成品作为当前默认参考。

```bash
# 1) 云端出素材（约 8–15 s 最稳；文案里别放 Java、27 这类混排）
python scripts/synthesize.py --voice pfa-cloud --text "<一段 40–70 字中文>" --output /tmp/ref.mp3
# 2) 转 24 kHz 单声道并登记
ffmpeg -i /tmp/ref.mp3 -ac 1 -ar 24000 /tmp/ref.wav
cp /tmp/ref.wav voices/<name>.wav    # ref_text 填上面那段文案
```

历次参考素材实测（同一句 18 字短句；下列 wav **除当前默认外均已删除**，数据只作选参时的经验）：

| 参考音频 | 时长 | 峰值 | 最安静 0.5 s 窗 | 本地短句结果 |
| --- | --- | --- | --- | --- |
| 原麦克风录音（已删，仅 DouyinWelcome 有副本） | 18.12 s | **1.000（已削波）** | 0.00654 | 4.13 s，长度正常；曾长期作为默认 |
| 云端净化 8.7 s（已删） | 8.70 s | 0.97 | 0.0012 量级 | 3.82 s，正常；吐字更清楚但音色偏了 |
| 该净化参考克隆出的 10.31 s 成品（**现默认 `voices/pfa.wav`**） | 10.31 s | 0.95 | 0.0587 | 3.42 s，正常 |
| 原始参考克隆出的 10.58 s 成品（已删） | 10.58 s | 0.95 | 0.0266 | 3.34 s，正常 |
| 云端净化 14.8 s（已删） | 14.79 s | 0.97 | 0.0012 量级 | 4.12 s，正常 |
| 云端净化 20.6 s（已删，废片） | **20.64 s** | 0.97 | 0.0012 量级 | **71.81 s 跑飞**，整段反复生成，不可用 |

结论：**长度是第一约束，超过 15 s 的参考能把短句直接带跑飞**，20.6 s 那条就是废片。音色与清晰度可以互换，用户 2026-11-04 优先保真人音色，2026-11-06 试听后又改口选定 10.31 s 成品参考，并删掉全部对照素材——即**清晰度优先，接受二次克隆的音色痕迹**。所以当前默认不再追求“最像本人原声”，而是这条固定参考；用户没开口就不要动它。

已知取舍：这条参考是模型生成物，句间不是真静音（最安静 0.5 s 窗 0.0587，明显高于云端净化素材的 0.0012 量级），若日后出现嘶声或含糊，先拆句而不是换参考。**整个过程中纳西妲的参考音频、逐字稿和别名从未改动。**

## 百炼自定义音色

云端合成 MP3，按 voice ID 计费。`--voice` 既吃音色表名也吃原始 voice ID：

```bash
python scripts/synthesize.py --voice pfa-cloud --text "你好，今天天气怎么样？" --output /absolute/path/output.mp3
```

需要 `dashscope>=2.0.1` 与环境变量 `DASHSCOPE_API_KEY`；不要把密钥写进脚本、日志、命令参数或交付物。若已登录 `bl` CLI，也可用 `bl speech synthesize`，并传入同一工作空间的 `--base-url`、模型与 voice ID。`bl speech synthesize --list-voices` 只列内置音色，查自定义音色要用 voice-enrollment 的 `list_voice`。模型、voice ID、工作空间必须匹配。用户点名走本地时不要为了“更稳”偷偷上传到云端。

## Breeze

用户明确点名 Breeze 才用；音色不在本技能的音色表里。默认音色 `voc_tkx6wc2cm8br`（2026-11-07 用户指定）、模型 `breeze-tts-2`，`--voice` / `--model` 可覆盖。文本会发送至 Breeze，可能产生费用。凭据优先读 `BREEZE_API_KEY`，否则从 macOS 钥匙串的 `codex-breeze-tts` / `BreezeBlue` 读取。运行环境 `~/.codex/venvs/breeze-tts`：

```bash
env -u NO_PROXY -u no_proxy ~/.codex/venvs/breeze-tts/bin/python scripts/synthesize_breeze.py --text "早上好呀，我是大飞鱼。" --output /absolute/path/output.mp3
```

`env -u` 不是可选项：本机 `NO_PROXY` 含 `[::1]`，`breeze_blue` 底层的 httpx 会把它解析成 host `:` + port `1]`，直接抛 `Invalid port: ':1]'`，一条音频都出不来。看到这条报错先查代理环境变量，别误判成 key 失效或音色 ID 不存在。输出为 24 kHz 单声道 128 kbps MP3。

## 落成音频资产

“生成哪个语音作为一个资产”= 产出一个可交付、可复用的音频文件，而不是聊天里的一句话。约定：

- 目录：`<项目>/voice-assets/<音色>/`，文件名 `<音色>-<yyyymmdd>-<用途>.wav`（本地）或 `.mp3`（云端），例如 `voice-assets/nahida/nahida-20261103-greeting.wav`。
- 只有试听、还没定用途时，写到同一目录并加 `-demo` 后缀，交付时说明“这是试听，定稿会替换”。
- 交付前自查：文件存在且非空、采样率与声道符合引擎、`soundfile` 读到的时长与文本长度相称、RMS 不接近 0（近静音就是合成失败）。
- 同一段文案要换音色对比时，输出文件名带音色，不要覆盖上一个。

## 边界

任一模式失败就报告原因，不自动切到另一模式；用户未授权时不克隆第三方声音、不上传参考录音。第三方角色音色（如纳西妲）只做私人与自用场景，公开传播要提示授权与 AI 标注。
