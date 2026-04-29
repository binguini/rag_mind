<template>
  <el-card v-if="visible" style="margin-top: 16px;">
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px;">
        <span>{{ title }}</span>
        <el-button size="small" text @click="$emit('close')">关闭</el-button>
      </div>
    </template>
    <div style="display: grid; gap: 12px;">
      <div><strong>任务ID：</strong>{{ taskId }}</div>
      <el-progress :percentage="displayedProgress" :status="progressStatus" />

      <div v-if="stageList.length > 0" class="progress-flow" :class="flowClass">
        <div v-for="(stage, index) in stageList" :key="stage.key" class="flow-item">
          <div class="flow-node" :class="stage.state">
            <span v-if="stage.state === 'done'">✓</span>
            <span v-else>{{ index + 1 }}</span>
          </div>
          <div class="flow-label" :class="stage.state">{{ stage.label }}</div>
          <div v-if="index < stageList.length - 1" class="flow-line" :class="lineState(index)"></div>
        </div>
      </div>

      <div class="stage-message">{{ message }}</div>
      <div><strong>状态：</strong>{{ statusLabel }}</div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export type TaskProgressStage = {
  key: string
  label: string
}

export type TaskProgressStatus = string

type StageState = 'done' | 'active' | 'pending'

defineEmits<{
  close: []
}>()

const props = defineProps<{
  visible: boolean
  title: string
  taskId: string
  progress: number
  status: TaskProgressStatus
  message: string
  stageKey?: string
  stages?: TaskProgressStage[]
  successStatuses?: string[]
  failedStatuses?: string[]
  statusLabel?: string
}>()

const normalizedStages = computed(() => props.stages ?? [])

const progressStatus = computed(() => {
  if ((props.failedStatuses ?? ['failed']).includes(props.status)) return 'exception'
  if ((props.successStatuses ?? ['completed']).includes(props.status)) return 'success'
  return undefined
})

const displayedProgress = computed(() => {
  const successStatuses = props.successStatuses ?? ['completed']
  if (successStatuses.includes(props.status)) return 100
  return props.progress
})

const currentStageIndex = computed(() => {
  const stages = normalizedStages.value
  if (stages.length === 0) return -1
  const currentKey = props.stageKey || ''
  const idx = stages.findIndex((stage) => stage.key === currentKey)
  return idx === -1 ? 0 : idx
})

const stageList = computed(() => {
  const stages = normalizedStages.value
  if (stages.length === 0) return [] as Array<TaskProgressStage & { state: StageState }>
  const currentIndex = currentStageIndex.value
  const successStatuses = props.successStatuses ?? ['completed']
  const isCompleted = successStatuses.includes(props.status)

  return stages.map((stage, index) => {
    let state: StageState = 'pending'
    if (isCompleted) {
      state = 'done'
    } else if (currentIndex === -1) {
      state = index === 0 ? 'active' : 'pending'
    } else if (index < currentIndex) {
      state = 'done'
    } else if (index === currentIndex) {
      state = 'active'
    }
    return { ...stage, state }
  })
})

const lineState = (index: number) => {
  const successStatuses = props.successStatuses ?? ['completed']
  if (successStatuses.includes(props.status)) return 'done'
  const currentIndex = currentStageIndex.value
  if (currentIndex === -1) return 'pending'
  return index < currentIndex ? 'done' : index === currentIndex ? 'active' : 'pending'
}

const flowClass = computed(() => ({
  'is-failed': (props.failedStatuses ?? ['failed']).includes(props.status),
  'is-completed': (props.successStatuses ?? ['completed']).includes(props.status),
}))
</script>

<style scoped>
.progress-flow {
  display: flex;
  align-items: flex-start;
  gap: 0;
  overflow-x: auto;
  padding: 8px 4px 4px;
}

.flow-item {
  display: flex;
  align-items: center;
  position: relative;
  min-width: 0;
}

.flow-node {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #909399;
  flex: 0 0 auto;
}

.flow-node.done,
.flow-node.active {
  border-color: #67c23a;
  background: #67c23a;
  color: #fff;
}

.flow-node.pending {
  background: #f5f7fa;
}

.flow-label {
  margin-left: 8px;
  font-size: 13px;
  color: #909399;
  white-space: nowrap;
}

.flow-label.done,
.flow-label.active {
  color: #303133;
  font-weight: 600;
}

.flow-line {
  width: 56px;
  height: 2px;
  background: #dcdfe6;
  margin: 0 12px;
  flex: 0 0 auto;
}

.flow-line.done,
.flow-line.active {
  background: #67c23a;
}

.stage-message {
  color: #606266;
}

.is-failed .flow-node.active,
.is-failed .flow-node.done {
  border-color: #f56c6c;
  background: #f56c6c;
}

.is-failed .flow-line.active,
.is-failed .flow-line.done {
  background: #f56c6c;
}
</style>
