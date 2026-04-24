# Vibe Sentinel - 屏幕活动监控报警器

## 项目概述
监控屏幕画面变化，当检测到画面静止超过阈值时自动发出蜂鸣报警，确保不会错过需要决策的时机。

## 核心功能
- 实时监控屏幕画面像素变化
- 空闲超时检测（画面静止）
- 蜂鸣报警系统
- 可配置的阈值和报警模式
- 支持多显示器监控

## 技术栈
- Python 3.9+
- mss: 高性能屏幕截图
- numpy: 图像像素比较
- winsound: Windows蜂鸣
- argparse: CLI参数解析

## 约束条件
- [execute] Windows平台优先
- [execute] 使用mss进行屏幕截图
- [execute] 使用numpy进行图像差异计算
- [verify] 所有功能需要可独立测试

## 目标用户
- 使用Claude Code进行vibe coding的开发者
- 需要及时响应AI助手提示的场景
