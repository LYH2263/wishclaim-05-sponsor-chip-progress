<template>
  <div class="wall">
    <h1 class="serif">愿望墙</h1>
    <p class="tag">无顶栏 · 瀑布流 · 点卡片认领</p>
    <div class="masonry">
      <article v-for="w in rows" :key="w.id" class="card" @click="$router.push('/wishes/'+w.id)">
        <span v-if="w.progress && w.progress.has_target" class="corner" :class="{ on: w.progress.reached }">
          {{ w.progress.percent }}%
        </span>
        <h3>{{ w.title || '（无标题）' }}</h3>
        <p>{{ w.note }}</p>
        <ProgressBar v-if="w.progress" :progress="w.progress" />
        <span class="tag">{{ w.status }} · {{ w.data_quality }}</span>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import ProgressBar from '../components/ProgressBar.vue'
const rows = ref([])
onMounted(async () => { rows.value = await api('/wishes') })
</script>
