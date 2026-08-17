# Lanerc Macast Bridge

让 Lanerc 的 DLNA 投屏在 Windows 电脑上通过
[Macast](https://github.com/xfangfang/Macast) 正常播放。

## 问题原因

Lanerc 的部分 HLS 视频分片以 `.jpg` 命名，并在 MPEG-TS 数据前附加一个很小的
JPEG 文件。Macast v0.7 内置的 mpv/FFmpeg 会把它误判为 MJPEG，随后提示：

```text
File error
no audio or video data played
```

本项目在 Macast 和播放器之间运行一个仅监听 `127.0.0.1` 的临时代理：

1. 重写 HLS 播放清单，隐藏会导致旧 FFmpeg 误判的 `.jpg` 文件名。
2. 检测 JPEG 结束标记及 MPEG-TS 同步字节。
3. 在内存中移除 JPEG 前缀，将标准 MPEG-TS 数据传给播放器。

视频采用边下边播方式，不会保存为完整视频文件。

## 要求

- Windows 10 或 Windows 11
- [Macast v0.7](https://github.com/xfangfang/Macast/releases/tag/v0.7)
- 可选：[PotPlayer](https://potplayer.daum.net/)
- 电视中转需要 [FFmpeg](https://ffmpeg.org/)

## 安装

退出 Macast，在 PowerShell 中运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

重新启动 Macast。安装器会选择 `Lanerc Cast Pro`，其默认输出为本机播放：

1. 检测到 PotPlayer 时优先使用 PotPlayer。
2. 否则使用 Macast 自带的 mpv。

所有渲染器都会保留在 Macast 托盘菜单的“选择播放器”中，可以手动切换。
随后在 Lanerc 中像投电视一样选择 Macast 设备即可。

安装后会提供统一的专业版渲染器及三个兼容渲染器：

- `Lanerc Cast Pro`：统一管理本机播放器与独立电视中转功能。
- `Lanerc PotPlayer Renderer`：在电脑 PotPlayer 播放。
- `Lanerc MPV Renderer`：在电脑内置 mpv 播放。
- `Lanerc TV Renderer`：由电脑转码并二次投屏到 DLNA 电视。

安装器会先将原配置备份到 Macast 配置目录下的 `backup` 文件夹。

## 专业版控制台

打开 [http://127.0.0.1:4380/](http://127.0.0.1:4380/)，或从 Macast 托盘菜单选择
`Open Control Panel`。控制台支持：

- 在 PotPlayer 和 Macast MPV 之间切换本机播放器；
- 将电视中转作为独立输出方式启用或关闭；
- 实时刷新同一局域网中的 DLNA 电视；
- 选择并保存目标电视。
- 可将视频单独送往电视，声音通过电脑默认音频设备（包括蓝牙耳机）播放。

Macast 的 DLNA 广播名称保持标准设备名称，不会随输出方式变化。切换输出方式对下一次
播放生效，正在播放的媒体会先停止。

## 电脑中转到电视

先安装 FFmpeg，然后在专业版控制台中选择“电视中转”和目标电视。Lanerc 仍然投屏到
Macast，电脑会：

1. 自动发现同一局域网中的 DLNA 电视；
2. 修复 Lanerc 的特殊 HLS 分片；
3. 转码为 H.264 + AAC + MPEG-TS；
4. 将本地 HTTP 流推送到电视。

可在 `macast_setting.json` 中设置：

```json
{
  "LanercTVIP": "192.168.1.100",
  "LanercFFmpegPath": "D:\\ffmpeg\\bin\\ffmpeg.exe",
  "LanercRelayPort": 8765
}
```

- `LanercTVIP` 留空时自动选择发现的第一台非 Macast 渲染器。
- `LanercRelayPort` 为 `0` 时自动选择空闲端口。
- Windows 防火墙需要允许 Macast 在专用网络接受电视的 HTTP 连接。

## 卸载

退出 Macast 后运行：

```powershell
.\uninstall.ps1
```

## 工作方式

```text
Lanerc --DLNA--> Macast --local HLS bridge--> PotPlayer / mpv
                                      |
                                      +--> FFmpeg --> DLNA TV
```

- 代理只接受本机连接。
- 上游地址以 SHA-256 标识存放在内存中，不会出现在本地播放 URL 中。
- 普通 MP4 等非 HLS 媒体仍走播放器原有路径。

## 已知限制

- PotPlayer 渲染器支持播放和停止；DLNA 暂停、音量同步等控制受 PotPlayer 接口限制。
- 电视中转依赖电视实现标准 UPnP AVTransport，并会产生数秒延迟。
- 音视频分离会同时建立电视视频流和电脑音频播放，网络与 CPU 占用略高。
- 1080p 软件转码会占用较多 CPU；当前默认使用兼容性最高的 `libx264`。
- 本项目针对 Macast v0.7 和当前观察到的 Lanerc HLS 分片格式。

## License

[MIT](LICENSE)
