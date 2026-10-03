<template>
  <div class="wall">
    <h1 class="serif">已完成</h1>
    <article v-for="w in rows" :key="w.id" class="card" @click="$router.push('/wishes/'+w.id)">
      <h3>{{ w.title }}</h3>
      <p>{{ w.claimer }}</p>
      <ProgressBar v-if="w.progress" :progress="w.progress" />
      <span class="tag">
        核销时累计 {{ w.pledged_snapshot ?? w.progress?.pledged ?? 0 }}
        <template v-if="w.target_snapshot != null"> / 目标快照 {{ w.target_snapshot }}</template>
      </span>
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import ProgressBar from '../components/ProgressBar.vue'
const rows = ref([])
onMounted(async () => { rows.value = await api('/done') })
</script>
