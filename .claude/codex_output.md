时间：2026-02-18 11:17

1) **UI 呈现建议/已落地实现**
- `area_group`（ExclusiveGroupWidget）：用 `RadioSet` 单选；若 API 未给选项则降级为普通输入（避免空白）。见 `src/ui/widgets/dynamic_form_field.py:227`、`src/ui/widgets/dynamic_form_field.py:717`
- `global`（FreeEditionWidget）：用 `Switch` 布尔开关，并展示 `details.text` 说明。见 `src/ui/widgets/dynamic_form_field.py:205`
- `area`（GeographicExtentWidget）：用 4 个输入框（N/W/S/E），仅在 4 个值都合法时才触发更新（避免约束抖动）。见 `src/ui/widgets/dynamic_form_field.py:259`、`src/ui/widgets/dynamic_form_field.py:810`
- `licences`（LicenceWidget）：用一组 `Checkbox`（按 `licences[*].id/label` 渲染），选中后回传已勾选的 licence id 列表。见 `src/ui/widgets/dynamic_form_field.py:284`

2) **FieldType 枚举是否需要扩展？**
- 需要：新增 `BOOLEAN / EXCLUSIVE_GROUP / GEO_EXTENT / LICENCE`，用于把“无 values 列表的特殊控件”从普通字符串数组里区分出来，便于默认值、取值与 UI 渲染一致。见 `src/core/dataset_schema.py:12`

3) **如何修改 `_parse_field_type` 与 `_get_initial_constraints`？**
- `_parse_field_type`：优先按 `widget type` 识别上述 4 类，再用 `schema.type` 兜底（支持 `boolean`、以及 `object` 且含 `n/s/e/w` 结构识别为地理范围）。见 `src/core/dataset_schema.py:70`
- `_get_initial_constraints`：对缺失 `details.values` 的字段补全可选项来源：
  - `LicenceWidget`：从 `details.licences[*].id` 提取
  - `ExclusiveGroupWidget`：尝试从 `details.options/choices/items` 或 `schema.enum/oneOf/anyOf` 提取
  见 `src/api/ecmwf_datastores_client.py:293`、`src/api/ecmwf_datastores_client.py:357`

4) **DynamicFieldWidget 是否需要支持新的输入类型？**
- 需要：已新增 `Switch/RadioSet/Checkbox/GeoExtent(4-input)` 的渲染、事件与 `get/set/clear/loading` 处理，并修正 Select 空值语义（把 `Select.BLANK` 当作“未选中”）。见 `src/ui/widgets/dynamic_form_field.py:423`、`src/ui/widgets/dynamic_form_field.py:433`、`src/ui/widgets/dynamic_form_field.py:444`
- 额外互斥增强：当 `area_group` 选择 `global/area` 时，自动与 `global`/`area` 字段保持互斥（清空并禁用另一侧）。见 `src/ui/widgets/contents/config_content.py:345`

补充：为避免“API 未提供可选值时误删用户输入”，`DynamicFormField.set_values` 改为仅在 `values` 非空时才过滤已选值。见 `src/core/dataset_schema.py:230`