# scripts

这里只有一个只读检查脚本：`probe_corpus.py`。

它读取正在运行的 AbstractTV V2 语料库，用于核对词条、例句和变体；不会生成、改写或写入任何语料。

```bash
python scripts/probe_corpus.py 孝
python scripts/probe_corpus.py 闹麻了 --api-base https://your-host/v2
```

站点自己的审核、媒体和任务代码属于 AbstractTV 服务，不复制到这个 skill 仓库。
