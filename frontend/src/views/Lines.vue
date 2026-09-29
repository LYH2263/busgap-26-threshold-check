<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import {
  FIELD_BUNCH, FIELD_LARGE, FIELD_PLANNED,
  validateLineParams, type LineParamError,
} from '../lineValidation'

const rows = ref<any[]>([])
const formError = ref('')

function emptyDraft() {
  return { code: '', name: '', planned_headway_min: '', bunch_threshold: '', large_threshold: '' }
}

// 新建表单草稿
const creating = ref(false)
const createDraft = ref(emptyDraft())
const createErrors = ref<LineParamError[]>([])

// 行内改写：editId 为正在改写的线路 id；数字只存在草稿里，保存成功才写回行
const editId = ref<number | null>(null)
const editDraft = ref(emptyDraft())
const editErrors = ref<LineParamError[]>([])

function errMap(errors: LineParamError[]) {
  const m = new Map<string, LineParamError>()
  for (const e of errors) m.set(e.field, e)
  return m
}
const createErrMap = computed(() => errMap(createErrors.value))
const editErrMap = computed(() => errMap(editErrors.value))

async function load() {
  rows.value = await api('/lines')
}
onMounted(load)

function startCreate() {
  creating.value = true
  createDraft.value = emptyDraft()
  createErrors.value = []
  formError.value = ''
}
function cancelCreate() {
  creating.value = false
  createErrors.value = []
}

function startEdit(r: any) {
  editId.value = r.id
  editDraft.value = {
    code: r.code, name: r.name,
    planned_headway_min: String(r.planned_headway_min),
    bunch_threshold: String(r.bunch_threshold),
    large_threshold: String(r.large_threshold),
  }
  editErrors.value = []
  formError.value = ''
}
function cancelEdit() {
  // 放弃改写：草稿丢弃，表格数字本就没被动过
  editId.value = null
  editErrors.value = []
}

async function submitCreate() {
  formError.value = ''
  createErrors.value = validateLineParams(createDraft.value)
  if (!createDraft.value.code.trim()) {
    createErrors.value.push({ field: 'code', label: '编码', message: '编码不能为空' })
  }
  if (createErrors.value.length) return
  try {
    const created = await api('/lines', {
      method: 'POST',
      body: JSON.stringify({
        code: createDraft.value.code.trim(),
        name: createDraft.value.name.trim(),
        planned_headway_min: Number(createDraft.value.planned_headway_min),
        bunch_threshold: Number(createDraft.value.bunch_threshold),
        large_threshold: Number(createDraft.value.large_threshold),
      }),
    })
    rows.value.push(created)
    creating.value = false
  } catch (e) {
    await hydrateErrors(e, createErrors)
  }
}

async function submitEdit() {
  formError.value = ''
  editErrors.value = validateLineParams(editDraft.value)
  if (editErrors.value.length) return
  const id = editId.value!
  try {
    const updated = await api(`/lines/${id}`, {
      method: 'PUT',
      body: JSON.stringify({
        planned_headway_min: Number(editDraft.value.planned_headway_min),
        bunch_threshold: Number(editDraft.value.bunch_threshold),
        large_threshold: Number(editDraft.value.large_threshold),
      }),
    })
    // 只有保存成功，页上数字才从改前值换成新值
    const idx = rows.value.findIndex(r => r.id === id)
    if (idx >= 0) rows.value[idx] = updated
    editId.value = null
  } catch (e) {
    // 被拒：行内数字保持改前（表格仍绑定 rows 中的旧值）
    await hydrateErrors(e, editErrors)
  }
}

async function hydrateErrors(e: unknown, sink: { value: LineParamError[] }) {
  // api() 对非 2xx 抛出的是「错误体文本」，尝试取出服务端同词字段错误
  const text = e instanceof Error ? e.message : String(e)
  try {
    const parsed = JSON.parse(text)
    const detail = parsed?.detail
    if (detail && typeof detail === 'object' && Array.isArray(detail.errors)) {
      sink.value = detail.errors
      formError.value = detail.message || '线路参数校验未通过'
      return
    }
  } catch { /* 非结构化错误体，走通用提示 */ }
  formError.value = text || '提交失败'
}

const fieldMeta = [
  { key: FIELD_PLANNED, label: '班距计划(分)' },
  { key: FIELD_BUNCH, label: '近车阈' },
  { key: FIELD_LARGE, label: '疏车阈' },
]
</script>
<template>
  <h1>线路</h1>
  <p class="sub">运营线路与近车阈 / 疏车阈判定参数 · 班距计划 &gt; 0，0 &lt; 近车阈 &lt; 班距计划，疏车阈 &gt; 班距计划</p>

  <div v-if="formError" class="form-banner">{{ formError }}</div>

  <div class="card">
    <table>
      <thead>
        <tr><th>编码</th><th>名称</th><th>班距计划(分)</th><th>近车阈</th><th>疏车阈</th><th>操作</th></tr>
      </thead>
      <tbody>
        <template v-for="r in rows" :key="r.id">
          <tr v-if="editId !== r.id">
            <td>{{ r.code }}</td>
            <td>{{ r.name }}</td>
            <td>{{ r.planned_headway_min }}</td>
            <td>{{ r.bunch_threshold }}</td>
            <td>{{ r.large_threshold }}</td>
            <td><button class="btn btn-mini" @click="startEdit(r)">改写</button></td>
          </tr>
          <tr v-else class="edit-row">
            <td>{{ r.code }}</td>
            <td>{{ r.name }}</td>
            <td v-for="f in fieldMeta" :key="f.key">
              <input
                v-model="editDraft[f.key as 'planned_headway_min']"
                :aria-label="f.label"
                :class="{ invalid: editErrMap.has(f.key) }"
                inputmode="decimal"
              />
              <div v-if="editErrMap.has(f.key)" class="field-err">{{ editErrMap.get(f.key)!.message }}</div>
            </td>
            <td class="edit-actions">
              <button class="btn btn-mini" @click="submitEdit">保存</button>
              <button class="btn btn-mini btn-ghost" @click="cancelEdit">取消</button>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>

  <div class="card" style="margin-top:1rem">
    <button v-if="!creating" class="btn" @click="startCreate">新建线路</button>
    <div v-else>
      <h2 style="margin:0 0 .5rem">新建线路</h2>
      <div class="create-grid">
        <label>编码
          <input v-model="createDraft.code" :class="{ invalid: createErrMap.has('code') }" />
          <div v-if="createErrMap.has('code')" class="field-err">{{ createErrMap.get('code')!.message }}</div>
        </label>
        <label>名称
          <input v-model="createDraft.name" />
        </label>
        <label v-for="f in fieldMeta" :key="f.key">
          {{ f.label }}
          <input
            v-model="createDraft[f.key as 'planned_headway_min']"
            inputmode="decimal"
            :class="{ invalid: createErrMap.has(f.key) }"
          />
          <div v-if="createErrMap.has(f.key)" class="field-err">{{ createErrMap.get(f.key)!.message }}</div>
        </label>
      </div>
      <div class="edit-actions" style="margin-top:.6rem">
        <button class="btn btn-mini" @click="submitCreate">创建</button>
        <button class="btn btn-mini btn-ghost" @click="cancelCreate">取消</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.btn-mini { padding: 0.2rem 0.6rem; font-size: 0.78rem; margin-right: 0.35rem; }
.btn-ghost { background: transparent; border: 1px solid var(--bg-dim); color: var(--bg-dim); }
input {
  width: 5.5rem; padding: 0.25rem 0.4rem; border-radius: 4px;
  border: 1px solid rgba(46,196,255,0.35); background: rgba(0,0,0,0.25);
  color: var(--bg-text); font: inherit;
}
input.invalid { border-color: var(--bg-red); }
.create-grid input { width: 100%; box-sizing: border-box; }
.create-grid { display: grid; grid-template-columns: repeat(5, minmax(6rem, 1fr)); gap: 0.75rem; }
.create-grid label { font-size: 0.78rem; color: var(--bg-dim); }
.field-err { color: var(--bg-red); font-size: 0.72rem; margin-top: 0.2rem; max-width: 12rem; }
.edit-actions { white-space: nowrap; }
.form-banner {
  margin-bottom: 0.75rem; padding: 0.5rem 0.75rem; border-radius: 4px;
  background: rgba(255,77,109,0.12); color: var(--bg-red); font-size: 0.85rem;
}
</style>
