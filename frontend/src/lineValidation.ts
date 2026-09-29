// 线路三参校验的前端镜像，规则与字段用词必须与后端
// backend/app/services/line_validation.py 完全一致：
//   班距计划 > 0；0 < 近车阈 < 班距计划；疏车阈 > 班距计划。
// 线路页提示与接口 400 回包共用同一套 field / label / message 用词。

export const FIELD_PLANNED = 'planned_headway_min'
export const FIELD_BUNCH = 'bunch_threshold'
export const FIELD_LARGE = 'large_threshold'

export const FIELD_LABELS: Record<string, string> = {
  [FIELD_PLANNED]: '班距计划',
  [FIELD_BUNCH]: '近车阈',
  [FIELD_LARGE]: '疏车阈',
}

export interface FieldError {
  field: string
  label: string
  message: string
}

function isFiniteNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

export function validateLineParams(
  plannedHeadwayMin: number,
  bunchThreshold: number,
  largeThreshold: number,
): FieldError[] {
  const raw: Record<string, unknown> = {
    [FIELD_PLANNED]: plannedHeadwayMin,
    [FIELD_BUNCH]: bunchThreshold,
    [FIELD_LARGE]: largeThreshold,
  }
  const values: Record<string, number> = {}
  const errors: FieldError[] = []
  for (const [field, value] of Object.entries(raw)) {
    if (!isFiniteNumber(value)) {
      errors.push({ field, label: FIELD_LABELS[field], message: `${FIELD_LABELS[field]}（分钟）必须是有限数字。` })
    } else {
      values[field] = value
    }
  }
  if (errors.length) return errors

  const planned = values[FIELD_PLANNED]
  const bunch = values[FIELD_BUNCH]
  const large = values[FIELD_LARGE]

  if (planned <= 0) {
    errors.push({ field: FIELD_PLANNED, label: FIELD_LABELS[FIELD_PLANNED],
      message: `班距计划（分钟）必须大于 0，当前为 ${planned}。` })
  }
  if (bunch <= 0) {
    errors.push({ field: FIELD_BUNCH, label: FIELD_LABELS[FIELD_BUNCH],
      message: `近车阈（分钟）必须大于 0，当前为 ${bunch}。` })
  } else if (bunch >= planned) {
    errors.push({ field: FIELD_BUNCH, label: FIELD_LABELS[FIELD_BUNCH],
      message: `近车阈必须小于班距计划（开区间 (0, 班距计划)），当前近车阈 ${bunch}、班距计划 ${planned}。` })
  }
  if (large <= planned) {
    errors.push({ field: FIELD_LARGE, label: FIELD_LABELS[FIELD_LARGE],
      message: `疏车阈必须严格大于班距计划，当前疏车阈 ${large}、班距计划 ${planned}。` })
  }
  return errors
}
