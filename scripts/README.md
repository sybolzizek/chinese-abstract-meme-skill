# scripts

这里有两个维护工具：

- `probe_corpus.py`：只读检查正在运行的 AbstractTV V2 语料库；
- `export_snapshot.py`：把已确认 V2 词条和关系导出为仓库内的 `data/corpus.json`。

它读取正在运行的 AbstractTV V2 语料库，用于核对词条、例句和变体；不会生成、改写或写入任何语料。

```bash
python scripts/probe_corpus.py 孝
python scripts/probe_corpus.py 闹麻了 --api-base https://your-host/v2
python scripts/export_snapshot.py --api-base http://127.0.0.1:8010/v2
```

前者不写入任何语料；后者只生成可审查、可提交的离线快照。站点自己的审核、媒体和任务代码仍属于 AbstractTV 服务，不复制到这个 skill 仓库。
