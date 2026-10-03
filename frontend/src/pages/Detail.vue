<template>
  <div class="wall">
    <h1 class="serif">{{ w.title }}</h1>
    <p>{{ w.note }}</p>
    <p class="tag">状态 {{ w.status }} · 认领人 {{ w.claimer || '—' }}</p>

    <ProgressBar v-if="w.progress" :progress="w.progress" />

    <section class="box" v-if="w.progress">
      <h3 class="serif">凑份子</h3>
      <input v-model="backer" placeholder="赞助人名字" />
      <input v-model.number="amount" type="number" min="0.01" step="0.01" placeholder="金额（单笔 &gt; 0）" />
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="ghost" :disabled="w.status==='fulfilled'" @click="preview">预览</button>
        <button :disabled="w.status==='fulfilled'" @click="confirm">确认赞助</button>
      </div>
      <p v-if="prev" class="tag">
        预览：累计 {{ prev.pledged_now }} → {{ prev.pledged_after }}
        <template v-if="prev.has_target"> · 缺口 {{ prev.remaining_now }} → {{ prev.remaining_after }}</template>
        <template v-if="prev.reached_after"> · 凑齐啦</template>
        <em>（不落库）</em>
      </p>
      <ul class="ledger" v-if="w.chipins && w.chipins.length">
        <li v-for="ch in w.chipins" :key="ch.id">
          <span>{{ ch.backer }}</span><span>{{ ch.amount }}</span>
        </li>
      </ul>
    </section>

    <section class="box" v-if="canEditTarget">
      <h3 class="serif">目标金额</h3>
      <input v-model.number="target" type="number" min="0.01" step="0.01" placeholder="留空表示无目标" />
      <button class="ghost" @click="saveTarget">保存目标</button>
      <p class="tag">仅未认领愿望可改；认领瞬间锁定快照，之后不回刷。</p>
    </section>

    <p v-if="err" class="err">{{ err }}</p>
    <input v-model="claimer" placeholder="你的名字" />
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button @click="claim">认领锁定</button>
      <button class="ghost" @click="release">释放</button>
      <button class="ghost" @click="fulfill">核销完成</button>
    </div>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import ProgressBar from '../components/ProgressBar.vue'
const props = defineProps({ id: String })
const w = ref({})
const claimer = ref('访客')
const backer = ref('访客')
const amount = ref(null)
const target = ref(null)
const prev = ref(null)
const err = ref('')
const canEditTarget = computed(() => ['open', 'released'].includes(w.value.status))

async function load() {
  w.value = await api('/wishes/' + props.id)
  target.value = w.value.progress?.target ?? w.value.target_amount ?? null
  prev.value = null
}
function chipinBody() { return { backer: backer.value, amount: Number(amount.value) } }

async function preview() {
  err.value = ''
  try { prev.value = await api('/wishes/' + props.id + '/chipin/preview', { method: 'POST', body: JSON.stringify(chipinBody()) }) }
  catch (e) { err.value = e.message }
}
async function confirm() {
  err.value = ''
  try { await api('/wishes/' + props.id + '/chipin/confirm', { method: 'POST', body: JSON.stringify(chipinBody()) }); amount.value = null; await load() }
  catch (e) { err.value = e.message }
}
async function saveTarget() {
  err.value = ''
  try { await api('/wishes/' + props.id + '/target', { method: 'PATCH', body: JSON.stringify({ target_amount: target.value === null || Number.isNaN(target.value) ? null : target.value }) }); await load() }
  catch (e) { err.value = e.message }
}
async function claim() {
  err.value=''; try { await api('/wishes/'+props.id+'/claim',{method:'POST',body:JSON.stringify({claimer:claimer.value})}); await load() } catch(e){ err.value=e.message }
}
async function release() {
  err.value=''; try { await api('/wishes/'+props.id+'/release',{method:'POST',body:'{}'}); await load() } catch(e){ err.value=e.message }
}
async function fulfill() {
  err.value=''; try { await api('/wishes/'+props.id+'/fulfill',{method:'POST',body:'{}'}); await load() } catch(e){ err.value=e.message === 'goal_not_reached' ? '还没凑齐目标，不能核销（仍保持认领）' : e.message }
}
onMounted(load)
</script>
