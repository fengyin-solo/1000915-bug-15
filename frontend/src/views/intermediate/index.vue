<template>
  <section class="page" data-module="intermediate">
    <header class="page-head">
      <div>
        <h2>中间液配制管理</h2>
        <p class="page-desc">围绕配制编号维护母液编号、目标浓度与定容体积，登记配制结论与领用记录；修改只保存在对应配制编号上。</p>
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
        <input v-model="keyword" placeholder="按配制编号检索" />
      </label>
      <label class="filter-item">
        <span>配制状态</span>
        <select v-model="statusFilter">
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
          <th>配制瓶数</th>
          <th>累计领用</th>
          <th>剩余瓶数</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <button v-if="column === '配制编号'" class="link" type="button" @click="openDetail(row)">
              {{ row[column] ?? '—' }}
            </button>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td>{{ row['配制瓶数'] ?? '—' }}</td>
          <td>{{ row['累计领用瓶数'] ?? 0 }}</td>
          <td>{{ row['剩余瓶数'] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openEdit(row)">编辑配制</button>
            <button
              v-if="row.status === '待配制'"
              class="link"
              type="button"
              @click="openPreparation(row)"
            >
              登记配制
            </button>
            <button
              v-if="row.status === '已配制'"
              class="link"
              type="button"
              @click="openRequisition(row)"
            >
              办理领用
            </button>
            <button
              v-if="row.status !== '已失效'"
              class="link danger"
              type="button"
              @click="runAction('标记失效', row)"
            >
              标记失效
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 4" class="empty-state">暂无中间液配制数据，可先登记中间液</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条中间液配制记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记 / 编辑配制 -->
    <div v-if="formVisible" class="modal-mask" @click.self="closeForm">
      <div class="modal">
        <h3 class="modal-title">{{ formMode === 'create' ? '登记中间液' : `编辑配制 ${form['配制编号']}` }}</h3>
        <div class="form-grid">
          <label class="form-item">
            <span>配制编号 <em>*</em></span>
            <input v-model="form['配制编号']" :disabled="formMode === 'edit'" placeholder="如 INTE-0004" />
          </label>
          <label class="form-item">
            <span>母液编号 <em>*</em></span>
            <input v-model="form['母液编号']" placeholder="如 STOCK-A01" />
          </label>
          <label class="form-item">
            <span>目标浓度 <em>*</em></span>
            <input v-model="form['目标浓度']" placeholder="如 0.5" />
          </label>
          <label class="form-item">
            <span>配制定容（定容体积）</span>
            <input v-model="form['配制定容']" placeholder="如 100mL" />
          </label>
          <label class="form-item">
            <span>配制日期</span>
            <input v-model="form['配制日期']" type="date" />
          </label>
          <label class="form-item">
            <span>失效日期</span>
            <input v-model="form['失效日期']" type="date" />
          </label>
          <label class="form-item">
            <span>配制人员</span>
            <input v-model="form['配制人员']" />
          </label>
          <label class="form-item">
            <span>配制瓶数</span>
            <input v-model.number="form['配制瓶数']" type="number" min="0" placeholder="登记配制前可补填" />
          </label>
        </div>
        <p v-if="formMode === 'edit'" class="form-tip">修改只保存在配制编号「{{ form['配制编号'] }}」上，不影响其它历史配制记录。</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeForm">取消</button>
          <button class="btn primary" type="button" :disabled="saving" @click="saveForm">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 登记配制结论 -->
    <div v-if="prepVisible" class="modal-mask" @click.self="prepVisible = false">
      <div class="modal">
        <h3 class="modal-title">登记配制结论 · {{ prepTarget?.['配制编号'] }}</h3>
        <div class="form-grid">
          <label class="form-item">
            <span>配制定容（定容体积）</span>
            <input v-model="prepForm['配制定容']" placeholder="如 100mL" />
          </label>
          <label class="form-item">
            <span>配制瓶数 <em>*</em></span>
            <input v-model.number="prepForm['配制瓶数']" type="number" min="1" />
          </label>
          <label class="form-item">
            <span>配制日期</span>
            <input v-model="prepForm['配制日期']" type="date" />
          </label>
          <label class="form-item">
            <span>失效日期</span>
            <input v-model="prepForm['失效日期']" type="date" />
          </label>
          <label class="form-item">
            <span>配制人员</span>
            <input v-model="prepForm['配制人员']" />
          </label>
          <label class="form-item">
            <span>配制结论 <em>*</em></span>
            <select v-model="prepForm['配制结论']">
              <option value="">请选择</option>
              <option value="合格">合格</option>
              <option value="不合格">不合格</option>
            </select>
          </label>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="prepVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="saving" @click="submitPreparation">
            {{ saving ? '提交中…' : '确认配制' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 领用登记弹窗：瓶数与配制结论同口径 -->
    <div v-if="reqVisible" class="modal-mask" @click.self="reqVisible = false">
      <div class="modal">
        <h3 class="modal-title">办理领用 · {{ reqTarget?.['配制编号'] }}</h3>
        <dl class="req-summary">
          <div><dt>母液编号</dt><dd>{{ reqTarget?.['母液编号'] }}</dd></div>
          <div><dt>目标浓度</dt><dd>{{ reqTarget?.['目标浓度'] }}</dd></div>
          <div><dt>配制结论</dt><dd>{{ reqTarget?.['配制结论'] || '—' }}</dd></div>
          <div><dt>配制瓶数</dt><dd>{{ reqTarget?.['配制瓶数'] ?? '—' }}</dd></div>
          <div><dt>已领用</dt><dd>{{ reqTarget?.['累计领用瓶数'] ?? 0 }} 瓶</dd></div>
          <div><dt>剩余瓶数</dt><dd>{{ reqTarget?.['剩余瓶数'] ?? '—' }}</dd></div>
        </dl>
        <div class="form-grid">
          <label class="form-item">
            <span>本次领用瓶数 <em>*</em></span>
            <input v-model.number="reqForm['领用瓶数']" type="number" min="1" :max="reqTarget?.['剩余瓶数'] ?? undefined" />
          </label>
          <label class="form-item">
            <span>领用人 <em>*</em></span>
            <input v-model="reqForm['领用人']" />
          </label>
          <label class="form-item">
            <span>领用日期</span>
            <input v-model="reqForm['领用日期']" type="date" />
          </label>
          <label class="form-item">
            <span>领用用途</span>
            <input v-model="reqForm['领用用途']" />
          </label>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="reqVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="saving" @click="submitRequisition">
            {{ saving ? '提交中…' : '确认领用' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 配制详情 -->
    <div v-if="detailVisible" class="modal-mask" @click.self="detailVisible = false">
      <div class="modal">
        <h3 class="modal-title">配制详情 · {{ detail?.['配制编号'] }}</h3>
        <dl class="req-summary">
          <div><dt>母液编号</dt><dd>{{ detail?.['母液编号'] }}</dd></div>
          <div><dt>目标浓度</dt><dd>{{ detail?.['目标浓度'] }}</dd></div>
          <div><dt>配制定容</dt><dd>{{ detail?.['配制定容'] || '—' }}</dd></div>
          <div><dt>配制日期</dt><dd>{{ detail?.['配制日期'] || '—' }}</dd></div>
          <div><dt>失效日期</dt><dd>{{ detail?.['失效日期'] || '—' }}</dd></div>
          <div><dt>配制人员</dt><dd>{{ detail?.['配制人员'] || '—' }}</dd></div>
          <div><dt>配制结论</dt><dd>{{ detail?.['配制结论'] || '—' }}</dd></div>
          <div><dt>配制状态</dt><dd>{{ detail?.['status'] }}</dd></div>
          <div><dt>配制瓶数</dt><dd>{{ detail?.['配制瓶数'] ?? '—' }}</dd></div>
          <div><dt>剩余瓶数</dt><dd>{{ detail?.['剩余瓶数'] ?? '—' }}</dd></div>
        </dl>
        <h4 class="modal-subtitle">领用记录</h4>
        <table v-if="detail?.['领用记录']?.length" class="data-table">
          <thead>
            <tr><th>领用日期</th><th>领用人</th><th>领用瓶数</th><th>领用用途</th></tr>
          </thead>
          <tbody>
            <tr v-for="(record, index) in detail?.['领用记录']" :key="index">
              <td>{{ record['领用日期'] }}</td>
              <td>{{ record['领用人'] }}</td>
              <td>{{ record['领用瓶数'] }}</td>
              <td>{{ record['领用用途'] || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty-state">暂无领用记录</p>
        <div class="modal-foot">
          <button class="btn primary" type="button" @click="detailVisible = false">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type RequisitionRecord = { 领用日期: string; 领用人: string; 领用瓶数: number; 领用用途: string }

const ENDPOINT = '/api/intermediate'
const columns = ['配制编号', '母液编号', '目标浓度', '配制定容', '配制日期', '失效日期', '配制人员', '配制状态']
const statuses = ['待配制', '已配制', '已领用', '已失效']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const saving = ref(false)
const keyword = ref('')
const statusFilter = ref('')

const pendingCount = ref(0)
const availableCount = ref(0)
const expiredCount = ref(0)
const stats = computed(() => [
  { label: '待配制数量', value: pendingCount.value },
  { label: '可用中间液', value: availableCount.value },
  { label: '已失效中间液', value: expiredCount.value },
])

const EMPTY_FORM = (): Row => ({
  配制编号: '',
  母液编号: '',
  目标浓度: '',
  配制定容: '',
  配制日期: '',
  失效日期: '',
  配制人员: '',
  配制瓶数: '',
})

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const form = ref<Row>(EMPTY_FORM())
const editingId = ref<number | null>(null)

const prepVisible = ref(false)
const prepTarget = ref<Row | null>(null)
const prepForm = ref<Record<string, string | number>>({})

const reqVisible = ref(false)
const reqTarget = ref<Row | null>(null)
const reqForm = ref<Record<string, string | number>>({ 领用瓶数: '', 领用人: '', 领用日期: '', 领用用途: '' })

const detailVisible = ref(false)
const detail = ref<(Row & { 领用记录?: RequisitionRecord[] }) | null>(null)

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (statusFilter.value) params.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('中间液列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '中间液配制列表读取失败'
  }
  await refreshStats()
}

async function refreshStats() {
  try {
    const [pending, prepared, received, expired] = await Promise.all(
      statuses.map((status) => countByStatus(status)),
    )
    pendingCount.value = pending
    availableCount.value = prepared + received
    expiredCount.value = expired
  } catch {
    // 统计失败不影响列表使用
  }
}

async function countByStatus(status: string): Promise<number> {
  const response = await request(`${ENDPOINT}?status=${encodeURIComponent(status)}&size=1`)
  if (!response.ok) return 0
  const payload = await response.json()
  return Number(payload.total ?? 0)
}

function openCreate() {
  formMode.value = 'create'
  form.value = EMPTY_FORM()
  editingId.value = null
  errorMessage.value = ''
  formVisible.value = true
}

function openEdit(row: Row) {
  formMode.value = 'edit'
  editingId.value = Number(row.id)
  // 每次都从行数据拷贝一份独立对象，避免弹窗之间共用同一份引用而串号
  form.value = { ...EMPTY_FORM(), ...row }
  errorMessage.value = ''
  formVisible.value = true
}

function closeForm() {
  formVisible.value = false
  editingId.value = null
}

async function saveForm() {
  errorMessage.value = ''
  const payload = { ...form.value }
  if (formMode.value === 'create') {
    if (!String(payload['配制编号'] || '').trim() || !String(payload['母液编号'] || '').trim() || !String(payload['目标浓度'] || '').trim()) {
      errorMessage.value = '配制编号、母液编号、目标浓度为必填项'
      return
    }
  }
  saving.value = true
  try {
    const url = formMode.value === 'create' ? ENDPOINT : `${ENDPOINT}/${editingId.value}`
    const method = formMode.value === 'create' ? 'POST' : 'PUT'
    const response = await request(url, { method, body: JSON.stringify({ values: payload }) })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result?.message || result?.detail || '保存未生效，请稍后重试')
    }
    formVisible.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '配制记录保存失败'
  } finally {
    saving.value = false
  }
}

function openPreparation(row: Row) {
  prepTarget.value = row
  prepForm.value = {
    配制定容: String(row['配制定容'] ?? ''),
    配制瓶数: row['配制瓶数'] ?? '',
    配制日期: String(row['配制日期'] ?? ''),
    失效日期: String(row['失效日期'] ?? ''),
    配制人员: String(row['配制人员'] ?? ''),
    配制结论: String(row['配制结论'] ?? ''),
  }
  errorMessage.value = ''
  prepVisible.value = true
}

async function submitPreparation() {
  if (!prepTarget.value) return
  errorMessage.value = ''
  saving.value = true
  try {
    const response = await request(`${ENDPOINT}/${prepTarget.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '登记配制', ...prepForm.value } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result?.message || '配制结论未保存，请稍后重试')
    }
    prepVisible.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '配制登记失败'
  } finally {
    saving.value = false
  }
}

function openRequisition(row: Row) {
  reqTarget.value = row
  reqForm.value = { 领用瓶数: '', 领用人: '', 领用日期: '', 领用用途: '' }
  errorMessage.value = ''
  reqVisible.value = true
}

async function submitRequisition() {
  if (!reqTarget.value) return
  errorMessage.value = ''
  saving.value = true
  try {
    const response = await request(`${ENDPOINT}/${reqTarget.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '办理领用', ...reqForm.value } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result?.message || '领用登记未生效，请稍后重试')
    }
    reqVisible.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '领用登记失败'
  } finally {
    saving.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  saving.value = true
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result?.message || '操作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '中间液操作失败'
  } finally {
    saving.value = false
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    const result = await response.json()
    if (!response.ok) {
      throw new Error(result?.detail || '配制详情读取失败')
    }
    detail.value = result
    detailVisible.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '配制详情读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.row-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
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
}
.modal {
  width: min(720px, 92vw);
  max-height: 88vh;
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2);
}
.modal-title {
  margin: 0 0 16px;
  font-size: 16px;
}
.modal-subtitle {
  margin: 16px 0 8px;
  font-size: 14px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}
.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}
.form-item input,
.form-item select {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  color: #1f2937;
}
.form-item em {
  color: #b42318;
  font-style: normal;
}
.form-tip {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--muted);
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.req-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px 16px;
  margin: 0 0 12px;
  font-size: 13px;
}
.req-summary div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  border-bottom: 1px dashed var(--border);
  padding-bottom: 4px;
}
.req-summary dt {
  color: var(--muted);
}
.req-summary dd {
  margin: 0;
  font-weight: 600;
}
</style>
