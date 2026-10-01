"""说明.txt at the data dir's root (PLAN 15.4.17): what each folder and file is, for someone who opens the
folder in Explorer rather than the app. Written when the data dir is opened, and again whenever the text changes."""

from pathlib import Path

NAME = "说明.txt"
TEXT = """Prometheus 知识库
=================

这个文件夹是 Prometheus 整理的知识库。软件会自动维护它，你也可以直接用资源管理器浏览。

一、每个分类一个文件夹，每个视频一个子文件夹
    <分类>\\_index.md                     这个分类里有哪些视频（标题、摘要、标签）
    <分类>\\<日期 标题>\\精读.html          精读报告，双击用浏览器打开，截图已内嵌
    <分类>\\<日期 标题>\\精读.md            精读的纯文字版，开头有标题、分类、标签、摘要
    <分类>\\<日期 标题>\\思维导图.md        导图大纲，可以导入 XMind、Obsidian
    <分类>\\<日期 标题>\\字幕.srt           带时间戳的字幕，播放器可以直接加载
    <分类>\\<日期 标题>\\字幕.txt           字幕纯文字，方便阅读和搜索
    <分类>\\<日期 标题>\\来源.url           双击打开原视频
    只生成了一部分的视频，文件夹里只有生成了的文件；没有精读时用视频标题命名。

二、给 AI 读
    llms.txt      总目录：所有分类和视频，从这里开始读
    index.json    所有视频的索引：标题、分类、标签、摘要、各文件的路径

三、软件自己用的
    .prometheus\\  数据库、设置（含 API Key）、转写模型、离线词典、日志。隐藏文件夹，请不要手动修改。

四、备份与迁移
    备份：把整个文件夹（连同隐藏的 .prometheus）复制走。
    换电脑：装好 Prometheus 后，在「设置 → 数据目录」里选这个文件夹就能接着用。
    在软件里改分类名、移动或删除视频时，文件夹会跟着变；在这里手动挪动的话，软件会提示「文件缺失」。
"""


def write(data_dir) -> None:
    target = Path(data_dir) / NAME
    if not target.is_file() or target.read_text(encoding="utf-8") != TEXT:
        target.write_text(TEXT, encoding="utf-8")
