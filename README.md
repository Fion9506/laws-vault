# laws-vault

**基于业务事实、提供可溯源依据的企业会计处理研究助手。**

输入交易事实或合同财务条款，识别会计问题，排查候选准则，整理原文依据和处理分支。本项目供研究和人工复核，不代表财政部或出版社的官方意见，不替代会计判断、审批或审计意见。

## 两个仓库

- 本仓库公开助手代码、Skills、规则、合成测试与使用说明，工作区位于 `assistant/`。
- [laws-vault-data](https://github.com/Fion9506/laws-vault-data) 为私有资料仓库，保存完整251份Markdown资料及清单。没有资料仓库访问权的使用者须自行准备有权使用的语料；克隆公开代码不包含这些正文。

代码目录与资料目录分离，不将本地旧Git历史、真实业务产物、日志、凭据或第三方工具仓库上传。本仓库不是独立模型服务或完整财务系统。

## 快速使用

```bash
git clone https://github.com/Fion9506/laws-vault.git
cd laws-vault/assistant
```

有资料访问权的维护者从私有仓库下载 `laws-vault-data-20261006.zip`，将压缩包内容解压到 `assistant/`：应出现 `cas/`、`casg/`、`casi/`、`casc/`、`casq/` 和 `scripts/state/manifest.json`。也可以导入自己有权使用的同格式资料。

在TraeWork桌面版以 `assistant/` 为本地项目根目录，确认 `.trae/rules/` 与 `.trae/skills/case-analysis/` 已加载，再提供企业准则体系、业务时点、交易和履行事实。核心研究路径不需要先安装MCP、向量数据库或嵌入API。

```bash
python -X utf8 scripts/health_check.py
python -X utf8 scripts/search_vault.py 质量保证 --layers cas,casi,casc,casq
python -m pip install pytest
python -X utf8 -m pytest tests/ -q -p no:cacheprovider
```

只使用本地Markdown不要求先安装Python；运行脚本和测试才需要Python。脚本文档声明3.10+，当前Windows/Python 3.14.3、pytest 9.0.2下173项离线测试通过，其他组合仍需验证。没有语料时不能出具依据；基础体检不能替代语料和业务核验。

## 适用范围与限制

适用于执行中国企业会计准则的收入、质保、租赁、补助、减值、预计负债和披露等研究。合同只是会计事实输入，不提供合同合法性、开票或纳税申报结论，不自动审批/过账。

这是研究工具alpha：历史版本、部分废止和分主体实施的规则仍需完善；引用主要依赖模型遵守规则和人工复核，没有完整程序化引用门禁，也未完成当前TraeWork全链路业务验收。173项脚本测试不是会计准确率。不要仅凭文件当前状态、采集日期或模型置信标注作最终会计判断。

## 来源、参考性质与异议

官方依据应逐份对应 [财政部会计司](https://kjs.mof.gov.cn/) 的发布原文；本地资料目前实际采集自 [MaoDocs审计文库](https://docs.maoyanqing.com/accounting/ent/)。每条依据区分官方出处核对状态、实际采集页、库内路径和真实核验记录，不将镜像或历史 `checked_at` 冒充官方核验。

第三方资料权利不因本项目代码采用MIT或标明来源而改变。完整资料仍保存在私有库；公开代码不捆绑指南书籍全文。资料和AI产物仅供参考，维护者负责发布范围与异议处置。

权利人可通过本仓库Issue提交相关文件路径和可核实的权利依据。维护者应及时核查，按实际情况更正、移除相关材料或暂停传播。不要在公开Issue上传身份证件、真实合同、客户账户或商业秘密。

## 说明

- [部署](assistant/docs/DEPLOYMENT.md)
- [使用](assistant/docs/USAGE.md)
- [数据来源与致谢](assistant/docs/SOURCES_AND_ACKNOWLEDGEMENTS.md)
- [参考与权利说明](assistant/docs/REFERENCE_AND_RIGHTS.md)
- [GitHub相近项目调研](assistant/docs/RELATED_PROJECTS.md)

原创代码、规则和说明采用MIT；该许可不授予第三方资料、出版物或上游组件的权利。
