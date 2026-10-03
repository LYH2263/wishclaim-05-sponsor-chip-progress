<template>
  <div class="wall">
    <h1 class="serif">我的认领</h1>
    <input v-model="name" @change="load" placeholder="认领人名" />
    <article v-for="w in rows" :key="w.id" class="card" @click="$router.push('/wishes/'+w.id)">
      <h3>{{ w.title }}</h3>
      <ProgressBar v-if="w.progress" :progress="w.progress" />
      <span class="tag">
        {{ w.status }} · 到期 {{ w.expires_at }}
        <template v-if="w.progress">
          · 赞助 {{ w.progress.pledged }}<template v-if="w.progress.has_target"> / {{ w.progress.target }}</template>
          · {{ w.chipin_count }} 笔
        </template>
      </span>
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import ProgressBar from '../components/ProgressBar.vue'
const name = ref('访客')
const rows = ref([])
async function load() { rows.value = await api('/mine?claimer=' + encodeURIComponent(name.value)) }
onMounted(load)
</script>
