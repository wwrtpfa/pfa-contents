# 抖音代码发布参考

本参考用于已经明确要求“上传/发布到抖音”的任务。它不负责启动浏览器或抖音 App，也不接管登录。

## 发布包

先创建归档目录：

```bash
python3 /Users/pengfanao/.codex/skills/self-media-video-producer/scripts/archive_media.py \
  --video /path/to/final.mp4 \
  --cover /path/to/cover.png \
  --title "标题" \
  --caption "正文" \
  --tags AI 视频 剪辑 \
  --extra /path/to/subtitles.srt \
  --extra /path/to/timeline.json
```

脚本输出一个新的目录，例如：

```text
/Users/pengfanao/Desktop/剪辑素材-视频/自媒体/20261105-153000-标题/
  video.mp4
  cover.png
  caption.md
  metadata.json
  archive-manifest.json
  upload-state.json
  extras/
```

## 现有登录窗口

默认前提是用户已经打开并登录 Google Chrome。技能在这个现有窗口中新建一个标签页，打开抖音创作者中心并上传；不得启动新的 Chrome 进程、新窗口、空白用户配置或自动登录。

如果环境提供 CDP，可额外使用以下地址：

```bash
export DOUYIN_CHROME_CDP_URL=http://127.0.0.1:9222
export DOUYIN_APP_CDP_URL=http://127.0.0.1:9223
export PLAYWRIGHT_NODE_PATH=/Users/pengfanao/.npm/_npx/9833c18b2d85bc59/node_modules
```

没有 CDP 时，使用浏览器插件/现有窗口控制，通过 DOM、无障碍控件和系统文件选择器上传；不得回退到截图坐标点击。只有当前 Chrome 窗口不存在或未登录时才停止。

## 上传命令

优先附着 Chrome：

```bash
node /Users/pengfanao/.codex/skills/self-media-video-producer/scripts/upload_douyin.mjs \
  --mode chrome-cdp \
  --archive-dir "/Users/pengfanao/Desktop/剪辑素材-视频/自媒体/<归档目录>"
```

默认命令只上传并停留在草稿状态，不点击发布。只有得到明确发布指令时，才额外传入 `--publish`。

只有 Chrome 不可用且抖音 App 自己暴露 Electron CDP 时才使用：

```bash
node /Users/pengfanao/.codex/skills/self-media-video-producer/scripts/upload_douyin.mjs \
  --mode douyin-app-cdp \
  --archive-dir "/Users/pengfanao/Desktop/剪辑素材-视频/自媒体/<归档目录>"
```

CDP 模式只调用 `connectOverCDP`，复用已有页面，不调用 `launch()` 或 `newPage()`；浏览器窗口模式只复用当前窗口并新建标签页。流程会把 `running`、`draft_ready`、`draft_unverified`、`submitted`、`submitted_unverified` 或 `failed` 写回 `upload-state.json`。CDP 地址只以脱敏形式写入状态文件，不保存 Cookie、Token 或账号凭据。

页面结构可能变化。找不到视频输入框、封面输入框、描述框或可用发布按钮时，脚本必须在点击发布前失败；归档内容保持不变，便于人工检查或下一次重试。
