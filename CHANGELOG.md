# Changelog

本项目遵循面向用户的版本记录。旧版本校验文件和构建产物保留在各自的 GitHub Release 中。

## [2.3.1] - 2026-08-18

### Added

- 正式 Windows 安装流程：自定义专用目录、正式启动入口、桌面/开始菜单快捷方式；
- Windows“已安装的应用”卸载注册；
- 安装器和正式入口的单实例保护；
- 电视中转的 PNG/JPEG 前缀 HLS 分片修复。

### Changed

- 安装器不再把卸载快捷方式放入开始菜单；
- 新版本不自动接管旧版安装目录，必须选择新的空目录；
- 电视中转通过 FFmpeg 输出更兼容的 H.264/AAC/MPEG-TS 流。

### Fixed

- 修复 FFmpeg 将带 PNG 图片头的 MPEG-TS 分片识别为 `png_pipe` 的问题；
- 修复电视端收到 `SetAVTransportURI` 和 `Play` 后首个 HLS 分片读取失败的问题。

## 历史版本

历史版本和对应校验文件请查看 [Releases](https://github.com/Asern-l/lanerc-cast-windows/releases)。
