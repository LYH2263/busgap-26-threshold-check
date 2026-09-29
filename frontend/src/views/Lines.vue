<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '../api'
import {
  validateLineParams,
  FIELD_PLANNED,
  FIELD_BUNCH,
  FIELD_LARGE,
  type FieldError,
} from '../lineValidation'

const rows = ref<any[]>([])

const editingId = ref<number | null>(null)
const draft = ref({ planned_headway_min: 0, bunch_threshold: 0, large_threshold: 0 })
const editErrors = ref<FieldError[]>([])
const editBusy = ref(false)

const createForm = ref({ code: '', name: '', planned_headway_min: 8, bunch_threshold: 3, large_threshold: 15 })
const createErrors = ref<FieldError[]>([])
const createBusy = ref(false)
const createNote = ref('')

function errFor(errs: FieldError[], field: string): string {
  return errs.filter((e) => e.field === field).map((e) => e.message).join(' ')
}

async function reload() { rows.value = await api('/lines') }
onMounted(reload)

function startEdit(r: any) {
  editingId.value = r.id
  editErrors.value = []
  draft.value = {
    planned_headway_min: r.planned_headway_min,
    bunch_threshold: r.bunch_threshold,
    large_threshold: r.large_threshold,
  }
}

function cancelEdit() {
  editingId.value = null
  editErrors.value = []
}

// 改写被拒（前端例程或接口 400）时，页上数字回到改前：draft 重置为该行现值。
function revertDraft(r: any) {
  draft.value = {
    planned_headway_min: r.planned_headway_min,
    bunch_threshold: r.bunch_threshold,
    large_threshold: r.large_threshold,
  }
}

async function saveEdit(r: any) {
  const errs = validateLineParams(
    draft.value.planned_headway_min, draft.value.bunch_threshold, draft.value.large_threshold,
  )
  editErrors.value = errs
  if (errs.length) { revertDraft(r); return }
  editBusy.value = true
  try {
    const saved = await api(`/lines/${r.id}`, { method: 'PUT', body: JSON.stringify(draft.value) })
    Object.assign(r, saved)
    editingId.value = null
  } catch (e) {
    if (e instanceof ApiError) {
      editErrors.value = e.payload?.detail?.errors ?? []
      if (!editErrors.value.length) editErrors.value = [{ field: '', label: '', message: String(e.message) }]
    }
    revertDraft(r)
  } finally { editBusy.value = false }
}

async function createLine() {
  createNote.value = ''
  const errs = validateLineParams(
    createForm.value.planned_headway_min, createForm.value.bunch_threshold, createForm.value.large_threshold,
  )
  createErrors.value = errs
  if (errs.length) return
  createBusy.value = true
  try {
    await api('/lines', { method: 'POST', body: JSON.stringify(createForm.value) })
    createForm.value.code = ''
    createForm.value.name = ''
    createNote.value = '已创建'
    await reload()
  } catch (e) {
    if (e instanceof ApiError) {
      createErrors.value = e.payload?.detail?.errors ?? []
      if (!createErrors.value.length) createErrors.value = [{ field: '', label: '', message: String(e.message) }]
    }
  } finally { createBusy.value = false }
}
</script>
<template>
  <h1>线路</h1>
  <p class="sub">运营线路与串车 / 大间隔判定阈值 · 班距计划 &gt; 0，0 &lt; 近车阈 &lt; 班距计划，疏车阈 &gt; 班距计划</p>

  <div class="card">
    <table>
      <thead>
        <tr><th>编码</th><th>名称</th><th>班距计划(分)</th><th>近车阈(分)</th><th>疏车阈(分)</th><th></th></tr>
      </thead>
      <tbody>
        <template v-for="r in rows" :key="r.id">
          <tr v-if="editingId !== r.id">
            <td>{{ r.code }}</td><td>{{ r.name }}</td>
            <td>{{ r.planned_headway_min }}</td><td>{{ r.bunch_threshold }}</td><td>{{ r.large_threshold }}</td>
            <td><button class="btn" @click="startEdit(r)">改写</button></td>
          </tr>
          <tr v-else class="ln-edit-row">
            <td>{{ r.code }}</td><td>{{ r.name }}</td>
            <td>
              <input v-model.number="draft.planned_headway_min" type="number" step="0.1"
                     :class="{ invalid: errFor(editErrors, FIELD_PLANNED) }" />
              <div v-if="errFor(editErrors, FIELD_PLANNED)" class="ln-err">{{ errFor(editErrors, FIELD_PLANNED) }}</div>
            </td>
            <td>
              <input v-model.number="draft.bunch_threshold" type="number" step="0.1"
                     :class="{ invalid: errFor(editErrors, FIELD_BUNCH) }" />
              <div v-if="errFor(editErrors, FIELD_BUNCH)" class="ln-err">{{ errFor(editErrors, FIELD_BUNCH) }}</div>
            </td>
            <td>
              <input v-model.number="draft.large_threshold" type="number" step="0.1"
                     :class="{ invalid: errFor(editErrors, FIELD_LARGE) }" />
              <div v-if="errFor(editErrors, FIELD_LARGE)" class="ln-err">{{ errFor(editErrors, FIELD_LARGE) }}</div>
            </td>
            <td>
              <button class="btn" :disabled="editBusy" @click="saveEdit(r)">保存</button>
              <button class="btn ln-cancel" @click="cancelEdit">取消</button>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>

  <h2 style="margin-top:1.25rem">新建线路</h2>
  <div class="card ln-create">
    <label>编码 <input v-model="createForm.code" placeholder="如 K58" /></label>
    <label>名称 <input v-model="createForm.name" placeholder="如 城西快线" /></label>
    <label>班距计划(分)
      <input v-model.number="createForm.planned_headway_min" type="number" step="0.1"
             :class="{ invalid: errFor(createErrors, FIELD_PLANNED) }" />
      <span v-if="errFor(createErrors, FIELD_PLANNED)" class="ln-err">{{ errFor(createErrors, FIELD_PLANNED) }}</span>
    </label>
    <label>近车阈(分)
      <input v-model.number="createForm.bunch_threshold" type="number" step="0.1"
             :class="{ invalid: errFor(createErrors, FIELD_BUNCH) }" />
      <span v-if="errFor(createErrors, FIELD_BUNCH)" class="ln-err">{{ errFor(createErrors, FIELD_BUNCH) }}</span>
    </label>
    <label>疏车阈(分)
      <input v-model.number="createForm.large_threshold" type="number" step="0.1"
             :class="{ invalid: errFor(createErrors, FIELD_LARGE) }" />
      <span v-if="errFor(createErrors, FIELD_LARGE)" class="ln-err">{{ errFor(createErrors, FIELD_LARGE) }}</span>
    </label>
    <button class="btn" :disabled="createBusy" @click="createLine">创建</button>
    <span v-if="createNote" class="ln-ok">{{ createNote }}</span>
  </div>
</template>
