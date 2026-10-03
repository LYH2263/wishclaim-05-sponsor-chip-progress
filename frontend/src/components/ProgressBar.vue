<template>
  <div class="fund" :class="{ done: p.reached && p.has_target }">
    <div class="fund-bar"><i :style="{ width: barWidth }" /></div>
    <span class="tag fund-label">
      <template v-if="p.has_target">
        凑份子 {{ p.pledged }} / {{ p.target }}（{{ p.percent }}%）
        <template v-if="p.reached"> · 已凑齐</template>
        <template v-else> · 缺口 {{ p.remaining }}</template>
      </template>
      <template v-else>赞助累计 {{ p.pledged }}</template>
    </span>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ progress: Object })
const p = computed(() => props.progress || { pledged: 0, has_target: false, percent: null, reached: false })
const barWidth = computed(() => (p.value.percent == null ? '0%' : p.value.percent + '%'))
</script>
