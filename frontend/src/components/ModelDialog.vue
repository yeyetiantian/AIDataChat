<template>
  <el-dialog v-model="visible" :title="title" :width="width" :top="top" destroy-on-close>
    <slot></slot>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(defineProps<{
  title?: string
  width?: string
  top?: string
}>(), {
  title: '弹框'
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const visible = ref(false)

const open = () => {
  visible.value = true
}

const close = () => {
  visible.value = false
}

defineExpose({
  open,
  close
})
</script>

<style scoped>

</style>
