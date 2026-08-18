# Contributing to Lanerc Cast

感谢参与。这个项目主要面向 Windows 10/11、Macast 0.7 和 DLNA 设备兼容性。

## 提交问题

请使用 GitHub Issue 模板，并尽量提供：

- Windows 版本和 Lanerc Cast 版本；
- 播放器、电视型号和网络拓扑；
- 可隐藏隐私后的日志片段；
- 稳定复现步骤和预期结果。

不要提交账号、Cookie、完整媒体地址、局域网外网地址或未经授权的第三方内容。

## 本地验证

```powershell
python -m unittest discover -s tests -v
```

涉及控制中心页面时，还应运行：

```powershell
python tests\playwright_pro.py
```

## Pull Request

PR 应保持单一目的，说明行为变化和验证结果。新增功能应同时补充测试和 README；不要提交 `build/`、`dist/`、`.build-venv/` 或本地运行时文件。
