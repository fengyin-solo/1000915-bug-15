<template>
  <section class="page" data-module="intermediate">
    <header class="page-head">
      <div>
        <h2>中间液配制管理</h2>
        <p class="page-desc">围绕配制编号登记、编辑、配制登记与领用：母液编号、目标浓度只挂在对应配制编号上，配制与领用结论全程同步。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记中间液</button>
        <button class="btn" type="button" @click="exportRows">导出中间液配制清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>配制编号</span>
        <input v-model="filters.keyword" placeholder="按配制编号检索" />
      </label>
      <label class="filter-item">
        <span>配制状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <template v-for="column in columns" :key="column">
            <td v-if="column === '配制编号'">
              <button class="link" type="button" @click="openDetail(row)">{{ row[column] || '—' }}</button>
            </td>
            <td v-else-if="column === '配制状态'">
              <span class="status-badge" :class="statusClass(String(row.status))">{{ row[column] ?? row.status ?? '—' }}</span>
            </td>
            <td v-else-if="column === '配制瓶数' || column === '剩余瓶数'">
              {{ row[column] === null || row[column] === undefined || row[column] === '' ? '—' : row[column] }}
            </td>
            <td v-else>{{ row[column] === null || row[column] === undefined || row[column] === '' ? '—' : row[column] }}</td>
          </template>
          <td class="row-actions">
            <button v-if="canEdit(row)" class="link" type="button" @click="openEdit(row)">编辑</button>
            <button v-if="canPrepare(row)" class="link" type="button" @click="openPrepare(row)">登记配制</button>
            <button v-if="canReceive(row)" class="link" type="button" @click="openReceive(row)">办理领用</button>
            <button v-if="row.status !== '已失效'" class="link danger" type="button" @click="markExpired(row)">标记失效</button>
            <button class="link" type="button" @click="openDetail(row)">详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无中间液配制数据，可先登记中间液</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条中间液配制记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="dialogMode" class="modal-mask" @click.self="closeDialog">
      <div class="modal-panel">
        <header class="modal-head">
          <h3>{{ dialogTitle }}</h3>
          <button class="modal-close" type="button" @click="closeDialog">×</button>
        </header>

        <!-- 详情：只读，配制结论、领用与修订记录都来自同一条配制编号 -->
        <div v-if="dialogMode === 'detail' && detailRow" class="modal-body">
          <dl class="detail-grid">
            <template v-for="column in detailColumns" :key="column">
              <dt>{{ column }}</dt>
              <dd v-if="column === '配制状态'">
                <span class="status-badge" :class="statusClass(String(detailRow.status))">{{ detailRow[column] ?? detailRow.status }}</span>
              </dd>
              <dd v-else>{{ displayValue(detailRow[column]) }}</dd>
            </template>
          </dl>

          <h4 class="section-title">领用记录（{{ receiveRecords.length }} 次）</h4>
          <table class="sub-table">
            <thead>
              <tr><th>时间</th><th>领用瓶数</th><th>领用人员</th><th>领用用途</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in receiveRecords" :key="index">
                <td>{{ item.时间 }}</td>
                <td>{{ item.领用瓶数 }}</td>
                <td>{{ item.领用人员 }}</td>
                <td>{{ item.领用用途 || '—' }}</td>
              </tr>
              <tr v-if="!receiveRecords.length">
                <td colspan="4" class="empty-state">暂无领用记录</td>
              </tr>
            </tbody>
          </table>

          <h4 class="section-title">修订记录（历史不可覆盖）</h4>
          <table class="sub-table">
            <thead>
              <tr><th>时间</th><th>动作</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in reviseRecords" :key="index">
                <td>{{ item.时间 }}</td>
                <td>{{ item.动作 }}</td>
                <td>{{ item.说明 }}</td>
              </tr>
              <tr v-if="!reviseRecords.length">
                <td colspan="3" class="empty-state">暂无修订记录</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 领用弹窗：展示的瓶数与配制结论以服务端记录为准 -->
        <div v-else-if="dialogMode === 'receive' && activeRow" class="modal-body">
          <dl class="detail-grid compact">
            <dt>配制编号</dt><dd>{{ activeRow.配制编号 }}</dd>
            <dt>配制结论</dt><dd>{{ activeRow.配制结论 || '尚未登记配制结论' }}</dd>
            <dt>配制瓶数</dt><dd>{{ displayValue(activeRow.配制瓶数) }}</dd>
            <dt>剩余瓶数</dt><dd><strong>{{ displayValue(activeRow.剩余瓶数) }}</strong></dd>
          </dl>
          <div class="form-grid">
            <label v-for="field in currentFields" :key="field.name" class="form-item">
              <span>{{ field.label }}<em v-if="field.required">*</em></span>
              <input
                v-model="form[field.name]"
                :type="field.type"
                :min="field.type === 'number' ? 1 : undefined"
                :step="field.type === 'number' ? 1 : undefined"
                :placeholder="field.placeholder ?? ''"
              />
            </label>
          </div>
          <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        </div>

        <!-- 登记 / 编辑 / 配制登记：同一套表单，字段随弹窗切换 -->
        <div v-else class="modal-body">
          <p v-if="dialogMode === 'edit' && activeRow" class="form-tip">
            配制编号 <strong>{{ activeRow.配制编号 }}</strong> 不可修改，母液编号与目标浓度只保存在这条配制编号上。
          </p>
          <div class="form-grid">
            <label v-for="field in currentFields" :key="field.name" class="form-item">
              <span>{{ field.label }}<em v-if="field.required">*</em></span>
              <input
                v-model="form[field.name]"
                :type="field.type"
                :min="field.type === 'number' ? 1 : undefined"
                :step="field.type === 'number' ? 1 : undefined"
                :disabled="dialogMode === 'edit' && field.name === '配制编号'"
                :placeholder="field.placeholder ?? ''"
              />
            </label>
          </div>
          <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        </div>

        <footer class="modal-foot">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button v-if="dialogMode !== 'detail'" class="btn primary" type="button" :disabled="saving" @click="saveDialog">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type ReceiveRecord = { 时间: string; 领用瓶数: number; 领用人员: string; 领用用途: string }
type ReviseRecord = { 时间: string; 动作: string; 说明: string }
type Row = {
  id: number
  status: string
  [key: string]: string | number | null | ReceiveRecord[] | ReviseRecord[] | undefined
}

type DialogMode = '' | 'create' | 'edit' | 'prepare' | 'receive' | 'detail'
type FieldType = 'text' | 'number' | 'date'
type FieldSchema = { name: keyof FormValues; label: string; type: FieldType; required?: boolean; placeholder?: string }
type FormValues = Record<string, string | number>

const ENDPOINT = '/api/intermediate'
const columns = ["配制编号", "母液编号", "目标浓度", "配制定容", "配制瓶数", "剩余瓶数", "配制结论", "配制日期", "失效日期", "配制人员", "配制状态"]
const statuses = ["待配制", "已配制", "已领用", "已失效"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = reactive<{ keyword: string; status: string }>({ keyword: '', status: '' })

const dialogMode = ref<DialogMode>('')
const activeRow = ref<Row | null>(null)
const detailRow = ref<Row | null>(null)
const form = ref<FormValues>({})
const dialogError = ref('')
const saving = ref(false)

const detailColumns = ["配制编号", "母液编号", "目标浓度", "配制定容", "配制瓶数", "剩余瓶数", "配制结论", "配制日期", "失效日期", "配制人员", "配制状态"]

const receiveRecords = computed<ReceiveRecord[]>(() => (detailRow.value?.领用记录 as ReceiveRecord[] | undefined) ?? [])
const reviseRecords = computed<ReviseRecord[]>(() => (detailRow.value?.修订记录 as ReviseRecord[] | undefined) ?? [])

const stats = computed(() => {
  const usable = rows.value.filter((row) => {
    const left = Number(row.剩余瓶数 ?? 0)
    return (row.status === '已配制' || row.status === '已领用') && left > 0
  }).length
  return [
    { label: '待配制数量', value: rows.value.filter((row) => row.status === '待配制').length },
    { label: '可用中间液', value: usable },
    { label: '已失效中间液', value: rows.value.filter((row) => row.status === '已失效').length },
  ]
})

const FIELD_SCHEMAS: Record<Exclude<DialogMode, '' | 'detail'>, FieldSchema[]> = {
  create: [
    { name: '配制编号', label: '配制编号', type: 'text', required: true, placeholder: '如 INTE-2026-005' },
    { name: '母液编号', label: '母液编号', type: 'text', required: true, placeholder: '如 MM-2026-0905' },
    { name: '目标浓度', label: '目标浓度', type: 'text', required: true, placeholder: '如 0.5 mg/L' },
    { name: '配制定容', label: '配制定容', type: 'text', placeholder: '如 500 mL' },
    { name: '配制日期', label: '配制日期', type: 'date' },
    { name: '失效日期', label: '失效日期', type: 'date' },
    { name: '配制人员', label: '配制人员', type: 'text' },
  ],
  edit: [
    { name: '配制编号', label: '配制编号', type: 'text' },
    { name: '母液编号', label: '母液编号', type: 'text', required: true },
    { name: '目标浓度', label: '目标浓度', type: 'text', required: true },
    { name: '配制定容', label: '配制定容', type: 'text' },
    { name: '失效日期', label: '失效日期', type: 'date' },
    { name: '配制人员', label: '配制人员', type: 'text' },
  ],
  prepare: [
    { name: '配制定容', label: '配制定容', type: 'text', required: true, placeholder: '如 500 mL' },
    { name: '配制瓶数', label: '配制瓶数', type: 'number', required: true },
    { name: '配制人员', label: '配制人员', type: 'text', required: true },
    { name: '配制日期', label: '配制日期', type: 'date', required: true },
    { name: '失效日期', label: '失效日期', type: 'date' },
  ],
  receive: [
    { name: '领用瓶数', label: '领用瓶数', type: 'number', required: true },
    { name: '领用人员', label: '领用人员', type: 'text', required: true },
    { name: '领用用途', label: '领用用途', type: 'text', placeholder: '如 水质检测' },
  ],
}

const currentFields = computed<FieldSchema[]>(() => {
  if (dialogMode.value === 'create' || dialogMode.value === 'edit' || dialogMode.value === 'prepare' || dialogMode.value === 'receive') {
    return FIELD_SCHEMAS[dialogMode.value]
  }
  return []
})

const dialogTitle = computed(() => {
  switch (dialogMode.value) {
    case 'create':
      return '登记中间液'
    case 'edit':
      return '编辑配制记录'
    case 'prepare':
      return '登记配制'
    case 'receive':
      return '办理领用'
    case 'detail':
      return '配制记录详情'
    default:
      return ''
  }
})

function today() {
  return new Date().toISOString().slice(0, 10)
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }
  return String(value)
}

function fieldValue(row: Row, name: string, fallback: string | number = ''): string | number {
  const value = row[name]
  return typeof value === 'string' || typeof value === 'number' ? value : fallback
}

function statusClass(status: string) {
  if (status === '待配制') return 'badge-pending'
  if (status === '已配制') return 'badge-ready'
  if (status === '已领用') return 'badge-received'
  if (status === '已失效') return 'badge-expired'
  return ''
}

function canEdit(row: Row) {
  return row.status === '待配制' || row.status === '已配制'
}

function canPrepare(row: Row) {
  return row.status === '待配制'
}

function canReceive(row: Row) {
  return (row.status === '已配制' || row.status === '已领用') && Number(row.剩余瓶数 ?? 0) > 0
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function closeDialog() {
  dialogMode.value = ''
  activeRow.value = null
  detailRow.value = null
  dialogError.value = ''
  form.value = {}
}

async function fetchRow(id: number): Promise<Row | null> {
  const response = await request(`${ENDPOINT}/${id}`)
  if (!response.ok) {
    return null
  }
  return (await response.json()) as Row
}

function openCreate() {
  dialogError.value = ''
  activeRow.value = null
  form.value = {
    配制编号: '',
    母液编号: '',
    目标浓度: '',
    配制定容: '',
    配制日期: today(),
    失效日期: '',
    配制人员: '',
  }
  dialogMode.value = 'create'
}

async function openEdit(row: Row) {
  dialogError.value = ''
  const fresh = await fetchRow(row.id)
  if (!fresh) {
    errorMessage.value = '配制记录读取失败，请刷新后重试'
    return
  }
  activeRow.value = fresh
  form.value = {
    配制编号: fieldValue(fresh, '配制编号'),
    母液编号: fieldValue(fresh, '母液编号'),
    目标浓度: fieldValue(fresh, '目标浓度'),
    配制定容: fieldValue(fresh, '配制定容'),
    失效日期: fieldValue(fresh, '失效日期'),
    配制人员: fieldValue(fresh, '配制人员'),
  }
  dialogMode.value = 'edit'
}

async function openPrepare(row: Row) {
  dialogError.value = ''
  const fresh = await fetchRow(row.id)
  if (!fresh) {
    errorMessage.value = '配制记录读取失败，请刷新后重试'
    return
  }
  activeRow.value = fresh
  form.value = {
    配制定容: fieldValue(fresh, '配制定容'),
    配制瓶数: fieldValue(fresh, '配制瓶数'),
    配制人员: fieldValue(fresh, '配制人员'),
    配制日期: fieldValue(fresh, '配制日期', today()),
    失效日期: fieldValue(fresh, '失效日期'),
  }
  dialogMode.value = 'prepare'
}

async function openReceive(row: Row) {
  dialogError.value = ''
  const fresh = await fetchRow(row.id)
  if (!fresh) {
    errorMessage.value = '配制记录读取失败，请刷新后重试'
    return
  }
  activeRow.value = fresh
  form.value = { 领用瓶数: '', 领用人员: '', 领用用途: '' }
  dialogMode.value = 'receive'
}

async function openDetail(row: Row) {
  dialogError.value = ''
  const fresh = await fetchRow(row.id)
  if (!fresh) {
    errorMessage.value = '配制记录读取失败，请刷新后重试'
    return
  }
  detailRow.value = fresh
  activeRow.value = fresh
  dialogMode.value = 'detail'
}

async function submitForm(method: string, url: string, body: Record<string, unknown>) {
  saving.value = true
  dialogError.value = ''
  try {
    const response = await request(url, { method, body: JSON.stringify(body) })
    let payload: { ok?: boolean; message?: string } | null = null
    try {
      payload = await response.json()
    } catch {
      payload = null
    }
    if (!response.ok) {
      throw new Error(payload?.message || `请求失败（${response.status}）`)
    }
    if (payload && payload.ok === false) {
      dialogError.value = payload.message || '操作未生效，请检查填写内容'
      return false
    }
    return true
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '中间液配制操作失败'
    return false
  } finally {
    saving.value = false
  }
}

async function saveDialog() {
  const mode = dialogMode.value
  const row = activeRow.value
  if (mode === 'create') {
    const ok = await submitForm('POST', ENDPOINT, { values: { ...form.value } })
    if (ok) {
      closeDialog()
      await reload()
    }
    return
  }
  if (!row) {
    return
  }
  if (mode === 'edit') {
    const values: FormValues = {}
    for (const field of FIELD_SCHEMAS.edit) {
      if (field.name === '配制编号') {
        continue
      }
      values[field.name] = form.value[field.name] ?? ''
    }
    const ok = await submitForm('PUT', `${ENDPOINT}/${row.id}`, { values })
    if (ok) {
      closeDialog()
      await reload()
    }
    return
  }
  if (mode === 'prepare') {
    const action = '登记配制'
    const ok = await submitForm('POST', `${ENDPOINT}/${row.id}/actions`, {
      values: { action, ...form.value },
    })
    if (ok) {
      closeDialog()
      await reload()
    }
    return
  }
  if (mode === 'receive') {
    const action = '办理领用'
    const ok = await submitForm('POST', `${ENDPOINT}/${row.id}/actions`, {
      values: { action, ...form.value },
    })
    if (ok) {
      closeDialog()
      await reload()
    }
  }
}

async function markExpired(row: Row) {
  if (!window.confirm(`确认将 ${row.配制编号} 标记为已失效？`)) {
    return
  }
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action: '标记失效' }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.message || '标记失效未生效')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '标记失效失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.keyword.trim()) {
    params.set('keyword', filters.keyword.trim())
  }
  if (filters.status) {
    params.set('status', filters.status)
  }
  const query = params.toString()
  try {
    const response = await request(query ? `${ENDPOINT}?${query}` : ENDPOINT)
    if (!response.ok) {
      throw new Error('中间液列表读取失败')
    }
    const payload = await response.json()
    rows.value = (payload.items ?? []) as Row[]
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '中间液配制列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.page-actions {
  display: flex;
  gap: 8px;
}
.filter-item select {
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  border: 1px solid transparent;
  white-space: nowrap;
}
.badge-pending {
  background: #f1f5f9;
  color: #475569;
  border-color: #cbd5e1;
}
.badge-ready {
  background: #e0ecff;
  color: #1d4ed8;
  border-color: #93b8fc;
}
.badge-received {
  background: #dcfce7;
  color: #15803d;
  border-color: #86efac;
}
.badge-expired {
  background: #fee2e2;
  color: #b42318;
  border-color: #fca5a5;
}
.link.danger {
  color: #b42318;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 24px;
}
.modal-panel {
  width: min(860px, 100%);
  max-height: 88vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 18px 50px rgba(15, 23, 42, 0.25);
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}
.modal-head h3 {
  margin: 0;
  font-size: 16px;
}
.modal-close {
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: var(--muted);
  cursor: pointer;
}
.modal-body {
  padding: 16px 18px;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid var(--border);
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 16px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item em {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.form-item input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.form-item input:disabled {
  background: #f1f5f9;
  color: var(--muted);
}
.form-tip {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--muted);
}
.detail-grid {
  display: grid;
  grid-template-columns: 110px 1fr 110px 1fr;
  gap: 6px 12px;
  margin: 0 0 12px;
  font-size: 13px;
}
.detail-grid.compact {
  grid-template-columns: 90px 1fr 90px 1fr;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.section-title {
  margin: 14px 0 6px;
  font-size: 13px;
}
.sub-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.sub-table th,
.sub-table td {
  border: 1px solid var(--border);
  padding: 5px 8px;
  text-align: left;
}
</style>
