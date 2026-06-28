# PDF 解析监控项目

这是一个功能完整的 PDF 解析项目，集成了多种解析方式和全面的监控功能。

## 功能特性

- ✅ **多种解析方式**: 
  - MinerU (magic-pdf) - 高质量 PDF 解析
  - LangChain - 快速文本提取
- 🌐 **Web 管理后台**: 在线上传、解析、查看结果
- 📊 **性能监控**: 实时监控每个解析步骤的执行时间和内存使用情况
- 📝 **详细日志**: 记录解析过程的详细日志，支持控制台输出和文件保存
- 📈 **进度追踪**: 可视化显示解析进度条
- 📋 **性能报告**: 自动生成 JSON 格式的性能报告
- 📄 **结果展示**: 完整的文本内容和结构化信息展示

## 项目结构

```
advanced_rag/
├── requirements.txt          # 项目依赖
├── README.md                 # 项目说明文档
├── app.py                    # Web 管理后台（Flask）
├── pdf_parser.py             # MinerU 解析器
├── langchain_parser.py       # LangChain 解析器
├── result_viewer.py          # 结果查看器
├── monitor.py                # 监控装饰器和工具类
├── config.py                 # 配置管理
├── templates/                # Web 模板
│   ├── index.html           # 首页
│   └── result.html          # 结果页
├── logs/                     # 日志目录
├── output/                   # 解析结果输出目录
│   ├── text/                # 文本文件
│   └── structured/          # 结构化数据
├── uploads/                  # 上传文件目录
└── examples/                 # 示例脚本
    ├── parse_example.py      # MinerU 示例
    └── langchain_parse_example.py  # LangChain 示例
```

## 环境要求

- Python 3.12 及以上版本
- 已安装 MinerU 模型权重文件（首次使用需要下载）

## 安装步骤

### 1. 创建 Conda 环境

```bash
conda create -n mineru_env python=3.12 -y
conda activate mineru_env
```

### 2. 安装依赖

```bash
pip install -U "magic-pdf[full]" -i https://mirrors.aliyun.com/pypi/simple
pip install -r requirements.txt
```

### 3. 下载模型权重

根据 MinerU 官方文档下载并配置模型权重文件。

## 使用方法

### 方式 1: Web 管理后台（推荐）

1. **启动服务器**:
   ```bash
   conda activate mineru_env
   python app.py
   ```

2. **访问后台**: 在浏览器中打开 http://127.0.0.1:8080 或 http://localhost:8080
   
   > 注意：macOS 系统默认会占用 5000 端口（AirPlay Receiver），所以使用 8080 端口。

3. **上传并解析**: 拖拽或选择 PDF 文件，自动解析并查看结果

详细说明请查看 [ADMIN_README.md](ADMIN_README.md)

### 方式 2: LangChain 解析器（快速文本提取）

```python
from langchain_parser import LangChainPDFParser

# 创建解析器
parser = LangChainPDFParser(enable_monitoring=True)

# 解析 PDF
result = parser.parse_pdf("sample.pdf")

# 查看结果
print(result['text_content'])  # 完整文本
print(result['stats'])         # 统计信息
print(result['metadata'])      # 元数据
```

**命令行使用**:
```bash
python examples/langchain_parse_example.py examples/Sample1.pdf
```

### 方式 3: MinerU 解析器（高质量解析）

```python
from pdf_parser import PDFParser

parser = PDFParser(enable_monitoring=True)
result = parser.parse_pdf("sample.pdf")
```

**命令行使用**:
```bash
python examples/parse_example.py sample.pdf
```

## 监控功能

### 监控指标

解析过程中会自动记录以下指标：

- **执行时间**: 每个步骤的开始时间、结束时间和执行时长
- **内存使用**: 每个步骤的内存使用量（起始值、结束值、增量）
- **状态信息**: 每个步骤的成功/失败状态
- **错误信息**: 如果步骤失败，会记录详细的错误信息

### 日志输出

- **控制台输出**: 彩色实时日志，包含进度条
- **日志文件**: 详细的日志文件保存在 `logs/` 目录
- **性能报告**: JSON 格式的性能报告保存在输出目录

### 性能报告示例

```json
{
  "summary": {
    "total_duration_seconds": 12.34,
    "initial_memory_mb": 256.50,
    "final_memory_mb": 512.75,
    "total_memory_increase_mb": 256.25
  },
  "steps": {
    "classify": {
      "step_name": "classify",
      "description": "文档分类",
      "duration": 2.10,
      "memory_increase_mb": 64.20,
      "status": "success"
    },
    ...
  }
}
```

## 配置选项

可以通过修改 `config.py` 或设置环境变量来配置：

```python
# config.py
LOG_LEVEL = "INFO"                    # 日志级别
ENABLE_PROGRESS_BAR = True            # 是否显示进度条
ENABLE_PERFORMANCE_MONITORING = True  # 是否启用性能监控
DROP_MODE = "none"                    # 丢弃模式
```

## 解析步骤说明

MinerU 解析流程包含以下步骤：

1. **文档分类 (classify)**: 识别 PDF 文档类型
2. **布局分析 (analyze)**: 分析文档布局结构
3. **内容解析 (parse)**: 提取文本、图片、表格等内容
4. **生成 Markdown (markdown)**: 将解析结果转换为 Markdown 格式

每个步骤都会被监控，记录详细的性能指标。

## 注意事项

1. **模型权重**: 首次使用需要下载 MinerU 模型权重文件，请参考官方文档
2. **内存使用**: 解析大文件时可能占用较多内存，建议根据实际情况调整
3. **日志文件**: 日志文件会自动保存在 `logs/` 目录，建议定期清理
4. **输出目录**: 解析结果和性能报告会保存在指定的输出目录

## 故障排除

### 常见问题

1. **导入错误**: 确保已正确安装 `magic-pdf` 和相关依赖
2. **模型缺失**: 检查是否已下载模型权重文件
3. **内存不足**: 尝试解析较小的文件或增加系统内存
4. **编码错误**: 确保 PDF 文件格式正确

### 查看日志和解析结果

**查看解析过程监控日志**:
```bash
# 使用便捷脚本
bash view_parse_process.sh

# 或手动查看
cat logs/pdf_parser_*.log
```

**查看解析的文本内容**:
```bash
# 完整文本文件
cat output/text/Sample1.txt

# 特定页面
cat output/text/Sample1_pages/page_001.txt

# 结构化信息
cat output/structured/Sample1_info.json | python -m json.tool
```

## 开发

### 项目依赖

- `magic-pdf[full]`: MinerU PDF 解析库
- `psutil`: 系统资源监控
- `tqdm`: 进度条显示
- `colorama`: 控制台彩色输出

### 扩展功能

可以基于现有框架扩展以下功能：

- 批量处理多个 PDF 文件
- 自定义解析后处理逻辑
- 集成其他 PDF 解析工具
- Web API 接口

## 许可证

本项目使用 MIT 许可证。

## 参考资源

- [MinerU 官方文档](https://mineru.site)
- [magic-pdf GitHub](https://github.com/opendatalab/MinerU)

## 贡献

欢迎提交 Issue 和 Pull Request！

