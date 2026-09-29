// 线路三参数校验——与后端 app/services/line_validation.py 同规则、同字段、同用词。
// 字段 key 与 API 422 回包 errors[].field 完全一致，页面按此锚定提示。

export const FIELD_PLANNED = 'planned_headway_min'
export const FIELD_BUNCH = 'bunch_threshold'
export const FIELD_LARGE = 'large_threshold'

export const FIELD_LABELS: Record<string, string> = {
  [FIELD_PLANNED]: '班距计划',
  [FIELD_BUNCH]: '近车阈',
  [FIELD_LARGE]: '疏车阈',
}

export interface LineParamError {
  field: string
  label: string
  message: string
}

export interface LineParams {
  planned_headway_min: number
  bunch_threshold: number
  large_threshold: number
}

export function validateLineParams(p: {
  planned_headway_min: number | string
  bunch_threshold: number | string
  large_threshold: number | string
}): LineParamError[] {
  const errors: LineParamError[] = []
  const raw: Record<string, number | string> = {
    [FIELD_PLANNED]: p.planned_headway_min,
    [FIELD_BUNCH]: p.bunch_threshold,
    [FIELD_LARGE]: p.large_threshold,
  }
  const nums: Record<string, number> = {}

  for (const field of [FIELD_PLANNED, FIELD_BUNCH, FIELD_LARGE]) {
    const label = FIELD_LABELS[field]
    const v = raw[field]
    const n = typeof v === 'number' ? v : Number(v)
    if (v === '' || v === null || v === undefined || !Number.isFinite(n)) {
      errors.push({ field, label, message: `${label}必须为数字` })
    } else {
      nums[field] = n
    }
  }

  const headway = nums[FIELD_PLANNED]
  const bunch = nums[FIELD_BUNCH]
  const large = nums[FIELD_LARGE]

  if (headway !== undefined && headway <= 0) {
    errors.push({ field: FIELD_PLANNED, label: FIELD_LABELS[FIELD_PLANNED],
      message: `${FIELD_LABELS[FIELD_PLANNED]}必须大于 0（当前为 ${headway} 分钟）` })
  }
  if (bunch !== undefined && bunch <= 0) {
    errors.push({ field: FIELD_BUNCH, label: FIELD_LABELS[FIELD_BUNCH],
      message: `${FIELD_LABELS[FIELD_BUNCH]}必须大于 0（开区间下界，当前为 ${bunch} 分钟）` })
  }

  if (headway !== undefined && headway > 0) {
    if (bunch !== undefined) {
      if (bunch === headway) {
        errors.push({ field: FIELD_BUNCH, label: FIELD_LABELS[FIELD_BUNCH],
          message: `${FIELD_LABELS[FIELD_BUNCH]}必须严格小于${FIELD_LABELS[FIELD_PLANNED]}，不能等于${FIELD_LABELS[FIELD_PLANNED]}（均为 ${bunch} 分钟）` })
      } else if (bunch > headway) {
        errors.push({ field: FIELD_BUNCH, label: FIELD_LABELS[FIELD_BUNCH],
          message: `${FIELD_LABELS[FIELD_BUNCH]}必须小于${FIELD_LABELS[FIELD_PLANNED]}（当前近车阈 ${bunch} ≥ 班距计划 ${headway}）` })
      }
    }
    if (large !== undefined) {
      if (large === headway) {
        errors.push({ field: FIELD_LARGE, label: FIELD_LABELS[FIELD_LARGE],
          message: `${FIELD_LABELS[FIELD_LARGE]}必须严格大于${FIELD_LABELS[FIELD_PLANNED]}，不能等于${FIELD_LABELS[FIELD_PLANNED]}（均为 ${large} 分钟）` })
      } else if (large < headway) {
        errors.push({ field: FIELD_LARGE, label: FIELD_LABELS[FIELD_LARGE],
          message: `${FIELD_LABELS[FIELD_LARGE]}必须大于${FIELD_LABELS[FIELD_PLANNED]}（当前疏车阈 ${large} ≤ 班距计划 ${headway}）` })
      }
    }
  }

  return errors
}

// 解析接口 422 回包：兼容我们自定义 {detail:{errors:[...]}} 的形状
export async function parseApiErrors(res: Response): Promise<{ message: string; errors: LineParamError[] }> {
  let detail: any = null
  try { detail = (await res.json())?.detail } catch { /* 非 JSON 错误体 */ }
  if (detail && typeof detail === 'object' && Array.isArray(detail.errors)) {
    return { message: detail.message || '线路参数校验未通过', errors: detail.errors }
  }
  return { message: '线路参数校验未通过', errors: [] }
}
