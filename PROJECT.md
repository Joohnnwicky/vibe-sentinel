# Vibe Sentinel - 屏幕活动监控报警器

## 项目概述
监控屏幕活动状态，当检测到空闲超过阈值时自动发出蜂鸣报警，确保不会错过需要决策的时机。

## 核心功能
- 实时监控鼠标和键盘活动
- 空闲超时检测
- 蜂鸣报警系统
- 可配置的阈值和报警模式

## 技术栈
- Python 3.9+
- pynput: 跨平台输入监控
- winsound: Windows蜂鸣
- argparse: CLI参数解析

## 约束条件
- [execute] Windows平台优先
- [execute] 使用pynput进行活动检测
- [verify] 所有功能需要可独立测试

## 目标用户
- 使用Claude Code进行vibe coding的开发者
- 需要及时响应AI助手提示的场景
