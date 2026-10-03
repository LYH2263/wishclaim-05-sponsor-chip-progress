<template>
  <div class="wall">
    <h1 class="serif">发愿望</h1>
    <input v-model="title" placeholder="标题" />
    <textarea v-model="note" rows="4" placeholder="备注" />
    <input v-model.number="target" type="number" min="0.01" step="0.01" placeholder="凑份子目标（留空则无目标）" />
    <button @click="submit">发布</button>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
const router = useRouter()
const title = ref('')
const note = ref('')
const target = ref(null)
async function submit() {
  const payload = { title: title.value, note: note.value }
  if (target.value !== null && !Number.isNaN(target.value)) payload.target_amount = target.value
  const r = await api('/wishes', { method: 'POST', body: JSON.stringify(payload) })
  router.push('/wishes/' + r.id)
}
</script>
