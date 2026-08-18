# Contributing to Lanerc Cast for Windows

感谢参与。这个项目面向 Windows 10/11 和常见 DLNA 设备，重点是电脑本地播放、HLS 分片兼容和电视中转。

## 提交问题

请使用 GitHub Issue 模板，并提供：

- Lanerc Cast 版本、Windows 版本；
- 播放器、电视型号和网络拓扑；
- 删除隐私后的日志片段；
- 稳定复现步骤、实际结果和预期结果。

不要提交账号、Cookie、完整媒体地址、私人 IP 或未经授权的第三方内容。

## 本地验证

```powershell
python -m unittest discover -s tests -v
python tests\playwright_pro.py
```

## Pull Request

PR 应保持单一目的，说明行为变化、根因和验证结果。新增功能应同时补充测试和 README。不要提交 `build/`、`dist/`、`._build_runtime/` 或本地运行时文件。
