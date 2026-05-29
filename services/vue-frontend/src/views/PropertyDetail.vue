<template>
  <div class="p-6 max-w-5xl mx-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <RouterLink to="/properties" class="p-2 rounded-lg hover:opacity-80 transition" style="color: var(--text-muted); background: var(--surface-2)">
        <i class="pi pi-arrow-left text-sm"></i>
      </RouterLink>
      <div>
        <h1 class="text-xl font-bold" style="color: var(--text)">{{ property?.address || '…' }}</h1>
        <p class="text-xs" style="color: var(--text-muted)">{{ [property?.city, property?.state].filter(Boolean).join(', ') }}</p>
      </div>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8" v-if="property">
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--mint)">
        <div class="flex items-center justify-between mb-1">
          <p class="text-xs" style="color: var(--text-muted)">Current Value</p>
          <span v-if="!hasManualCurrentValue" class="text-[10px] px-1.5 py-0.5 rounded" style="background: rgba(96,165,250,0.15); color: #60a5fa">Estimated</span>
        </div>
        <template v-if="editingCurrentValue">
          <InputText
            v-model="currentValueDraft"
            type="number"
            step="0.01"
            min="0"
            class="w-full"
            placeholder="Enter current value"
            @keydown.enter.prevent="saveCurrentValue"
          />
          <div class="flex items-center gap-2 mt-2">
            <Button
              @click="saveCurrentValue"
              size="small"
              class="p-button-primary"
              label="Save"
              :loading="savingCurrentValue"
              :disabled="savingCurrentValue"
            />
            <Button
              @click="cancelEditCurrentValue"
              size="small"
              severity="secondary"
              text
              label="Cancel"
              :disabled="savingCurrentValue"
            />
          </div>
        </template>
        <template v-else>
          <p class="text-lg font-bold" style="color: var(--mint)">${{ fmt(displayCurrentValue) }}</p>
          <button
            @click="startEditCurrentValue"
            class="mt-2 text-[11px] px-2 py-1 rounded hover:opacity-80"
            style="background: var(--surface-2); color: var(--text-muted)"
          >
            Edit current value
          </button>
        </template>
        <p v-if="currentValueStatus" class="text-[11px] mt-1" style="color: var(--text-muted)">{{ currentValueStatus }}</p>
        <p v-if="!hasManualCurrentValue && analytics?.current?.market_estimate" class="text-[11px] mt-1" style="color: var(--text-muted)">
          Market proxy: ${{ fmt(analytics.current.market_estimate) }} · Improvements: ${{ fmt(analytics.current.improvement_spend) }}
        </p>
        <button
          v-if="!editingCurrentValue && !hasManualCurrentValue && analytics?.current?.effective_current_value"
          @click="applyEstimatedValue"
          :disabled="applyingEstimate"
          class="mt-2 text-[11px] px-2 py-1 rounded hover:opacity-80 disabled:opacity-40"
          style="background: var(--surface-2); color: var(--text-muted)"
        >
          {{ applyingEstimate ? 'Applying…' : 'Use as current value' }}
        </button>
        <button
          @click="enrichFromAddress"
          :disabled="enrichingAddress || savingCurrentValue"
          class="mt-2 ml-2 text-[11px] px-2 py-1 rounded hover:opacity-80 disabled:opacity-40"
          style="background: var(--surface-2); color: var(--text-muted)"
        >
          {{ enrichingAddress ? 'Fetching…' : 'Fetch address data' }}
        </button>
        <p v-if="enrichStatus" class="text-[11px] mt-1" style="color: var(--text-muted)">{{ enrichStatus }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Equity</p>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(displayEquity) }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <div class="flex items-center justify-between mb-1">
          <p class="text-xs" style="color: var(--text-muted)">Mortgage Balance</p>
          <div class="flex items-center gap-1">
            <span v-if="property.mortgage_account_id" class="text-xs px-1.5 py-0.5 rounded" style="background: rgba(61,219,184,0.15); color: var(--mint)">Plaid</span>
            <button v-if="property.mortgage_account_id" @click="syncMortgage" :disabled="syncing" title="Sync from Plaid" style="color: var(--mint)" class="hover:opacity-70 disabled:opacity-40">
              <i class="pi pi-refresh text-xs" :class="syncing ? 'animate-spin' : ''"></i>
            </button>
            <button v-if="property.mortgage_account_id" @click="unlinkMortgage" title="Unlink" style="color: var(--text-muted)" class="hover:opacity-70">
              <i class="pi pi-times text-xs"></i>
            </button>
            <template v-else>
              <button @click="showLinkMortgage = true" title="Link to Plaid" style="color: var(--text-muted)" class="hover:opacity-70">
                <i class="pi pi-link text-xs"></i>
              </button>
              <label :title="importingCsv ? 'Uploading…' : 'Import CSV or JSON'" style="color: var(--text-muted)" class="hover:opacity-70 cursor-pointer">
                <input type="file" accept=".csv,.json,text/csv,application/json" class="hidden" @change="handleImportFile" :disabled="importingCsv" />
                <i v-if="importingCsv" class="pi pi-spin pi-spinner text-xs"></i>
                <i v-else class="pi pi-file-import text-xs"></i>
              </label>
              <button @click="showCsvHelp = true" title="CSV format help" style="color: var(--text-muted)" class="hover:opacity-70">
                <i class="pi pi-question-circle text-xs"></i>
              </button>
            </template>
          </div>
        </div>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(property.mortgage_balance) }}</p>
        <p v-if="property.mortgage_account_id" class="text-xs mt-0.5 truncate" style="color: var(--text-muted)">{{ linkedAccountLabel }}</p>
      </div>
      <div class="rounded-xl border p-4" style="background: var(--surface); border-color: var(--border)">
        <p class="text-xs mb-1" style="color: var(--text-muted)">Monthly Payment</p>
        <p class="text-lg font-bold" style="color: var(--text)">${{ fmt(property.mortgage_payment) }}</p>
        <div class="mt-3">
          <p class="text-xs mb-1" style="color: var(--text-muted)">Interest Rate (%)</p>
          <InputText
            v-model.number="projectionInterestRate"
            type="number"
            min="0"
            step="0.001"
            class="w-full"
            placeholder="6.5"
          />
          <p class="text-[10px] mt-1" style="color: var(--text-muted)">Used by interest projection</p>
        </div>
      </div>
    </div>

    <!-- Debt + Equity trend -->
    <div class="rounded-xl border p-4 mb-8" style="background: var(--surface); border-color: var(--border)">
      <div class="flex items-center justify-between mb-3">
        <div>
          <p class="text-sm font-semibold" style="color: var(--text)">Debt & Equity Over Time</p>
          <p class="text-xs mt-0.5" style="color: var(--text-muted)">Debt line uses mortgage history imports + linked balance. Equity line uses value estimate and disclosed improvements.</p>
        </div>
        <select v-model.number="historyMonths" class="px-2 py-1.5 rounded-lg text-xs" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
          <option :value="12">12 months</option>
          <option :value="24">24 months</option>
          <option :value="36">36 months</option>
        </select>
      </div>

      <div v-if="loadingAnalytics" class="h-72 rounded animate-pulse" style="background: var(--surface-2)"></div>
      <div v-else-if="debtEquityChartData.labels.length" class="h-72">
        <Line :data="debtEquityChartData" :options="lineChartOptions" />
      </div>
      <div v-else class="h-72 rounded-lg border flex items-center justify-center text-xs" style="border-color: var(--border); color: var(--text-muted)">
        No history yet. Import mortgage CSV or add mortgage/improvement transactions to build trend data.
      </div>
    </div>

    <!-- Interest projection -->
    <div class="rounded-xl border p-4 mb-8" style="background: var(--surface); border-color: var(--border)">
      <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-3 mb-4">
        <div>
          <p class="text-sm font-semibold" style="color: var(--text)">Interest Projection</p>
          <p class="text-xs mt-0.5" style="color: var(--text-muted)">Compares cumulative interest with your current payment vs an extra monthly principal payment.</p>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 w-full lg:w-auto lg:min-w-[580px]">
          <div>
            <p class="text-[11px] mb-1" style="color: var(--text-muted)">Additional payment ($/mo)</p>
            <InputText
              v-model.number="additionalPrincipalPayment"
              type="number"
              min="0"
              step="1"
              class="w-full"
              placeholder="0"
            />
          </div>
          <div>
            <p class="text-[11px] mb-1" style="color: var(--text-muted)">Lump sum payment ($)</p>
            <InputText
              v-model.number="lumpSumPayment"
              type="number"
              min="0"
              step="1"
              class="w-full"
              placeholder="0"
            />
          </div>
          <div>
            <p class="text-[11px] mb-1" style="color: var(--text-muted)">Projection horizon</p>
            <select
              v-model.number="projectionMonths"
              class="w-full px-2 py-2 rounded-lg text-xs"
              style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)"
            >
              <option :value="60">5 years</option>
              <option :value="120">10 years</option>
              <option :value="180">15 years</option>
              <option :value="240">20 years</option>
              <option :value="360">30 years</option>
            </select>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4" v-if="!interestProjection.error">
        <div class="rounded-lg p-3" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Projected Interest (current)</p>
          <p class="text-sm font-bold mt-0.5" style="color: var(--text)">${{ fmt(interestProjection.baseline.totalInterestProjected) }}</p>
          <p class="text-[11px] mt-1" style="color: var(--text-muted)">Payoff: {{ payoffLabel(interestProjection.baseline.payoffMonth) }}</p>
        </div>
        <div class="rounded-lg p-3" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Projected Interest (extra plan)</p>
          <p class="text-sm font-bold mt-0.5" style="color: var(--text)">${{ fmt(interestProjection.withExtra.totalInterestProjected) }}</p>
          <p class="text-[11px] mt-1" style="color: var(--text-muted)">Payoff: {{ payoffLabel(interestProjection.withExtra.payoffMonth) }}</p>
        </div>
        <div class="rounded-lg p-3" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Projected Interest Saved</p>
          <p class="text-sm font-bold mt-0.5" style="color: var(--mint)">${{ fmt(projectedInterestSavings) }}</p>
          <p class="text-[11px] mt-1" style="color: var(--text-muted)">Plan: +${{ fmt(additionalPrincipalPayment) }}/mo · ${{ fmt(lumpSumPayment) }} once</p>
        </div>
      </div>

      <div v-if="interestProjection.error" class="h-72 rounded-lg border flex items-center justify-center text-xs px-4 text-center" style="border-color: var(--border); color: var(--text-muted)">
        {{ interestProjection.error }}
      </div>
      <div v-else-if="interestProjectionChartData.labels.length" class="h-72">
        <Line :data="interestProjectionChartData" :options="interestProjectionChartOptions" />
      </div>
      <p v-if="projectedEquityCurve.length" class="text-[11px] mt-2" style="color: var(--text-muted)">
        Equity curve assumes home value grows at {{ (projectionAnnualGrowthRate * 100).toFixed(1) }}% annually.
      </p>
      <div v-else class="h-72 rounded-lg border flex items-center justify-center text-xs" style="border-color: var(--border); color: var(--text-muted)">
        No projection available.
      </div>
    </div>

    <!-- Payment mix projection -->
    <div class="rounded-xl border p-4 mb-8" style="background: var(--surface); border-color: var(--border)">
      <div class="flex items-start justify-between mb-3">
        <div>
          <p class="text-sm font-semibold" style="color: var(--text)">Payment Mix Projection</p>
          <p class="text-xs mt-0.5" style="color: var(--text-muted)">Projected percent of each payment that goes to principal vs interest under amortization rules.</p>
        </div>
      </div>

      <div v-if="interestProjection.error" class="h-72 rounded-lg border flex items-center justify-center text-xs px-4 text-center" style="border-color: var(--border); color: var(--text-muted)">
        {{ interestProjection.error }}
      </div>
      <template v-else>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          <div class="rounded-lg p-3" style="background: var(--surface-2)">
            <p class="text-xs" style="color: var(--text-muted)">This Month (Current)</p>
            <p class="text-sm font-bold mt-0.5" style="color: var(--text)">
              Principal {{ fmtPct(paymentMixSummary.baselinePrincipalPct) }} · Interest {{ fmtPct(paymentMixSummary.baselineInterestPct) }}
            </p>
          </div>
          <div class="rounded-lg p-3" style="background: var(--surface-2)">
            <p class="text-xs" style="color: var(--text-muted)">This Month (Extra Plan)</p>
            <p class="text-sm font-bold mt-0.5" style="color: var(--text)">
              Principal {{ fmtPct(paymentMixSummary.withExtraPrincipalPct) }} · Interest {{ fmtPct(paymentMixSummary.withExtraInterestPct) }}
            </p>
          </div>
        </div>

        <div v-if="paymentMixChartData.labels.length" class="h-72">
          <Line :data="paymentMixChartData" :options="paymentMixChartOptions" />
        </div>
        <div v-else class="h-72 rounded-lg border flex items-center justify-center text-xs" style="border-color: var(--border); color: var(--text-muted)">
          No payment mix projection available.
        </div>
      </template>
    </div>

    <!-- Embedded plans + todos -->
    <div class="rounded-xl border p-4 mb-8" style="background: var(--surface); border-color: var(--border)">
      <div class="flex items-center justify-between mb-4">
        <div>
          <p class="text-sm font-semibold" style="color: var(--text)">Property Plan Workspace</p>
          <p class="text-xs mt-0.5" style="color: var(--text-muted)">Chat about this property and track execution in todos.</p>
        </div>
      </div>

      <div class="grid lg:grid-cols-12 gap-4">
        <aside class="lg:col-span-3 rounded-xl border p-3" style="border-color: var(--border); background: var(--surface-2)">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs font-semibold" style="color: var(--text)">Plans</p>
            <button @click="showNewPlanComposer = !showNewPlanComposer" class="text-xs px-2 py-1 rounded hover:opacity-80" style="background: rgba(61,219,184,0.18); color: var(--mint)">
              {{ showNewPlanComposer ? 'Close' : 'New' }}
            </button>
          </div>

          <div v-if="showNewPlanComposer" class="space-y-2 mb-3">
            <InputText v-model="newPlanTitle" class="w-full" placeholder="Plan title" />
            <Button @click="createPropertyPlan" size="small" class="p-button-primary w-full" :disabled="!newPlanTitle.trim()" :loading="creatingPropertyPlan" label="Create" />
          </div>

          <div v-if="loadingPropertyPlans" class="text-xs py-4 text-center" style="color: var(--text-muted)">Loading plans…</div>
          <div v-else-if="propertyPlans.length === 0" class="text-xs py-6 text-center" style="color: var(--text-muted)">No plans for this property yet.</div>
          <div v-else class="space-y-1">
            <div
              v-for="plan in propertyPlans"
              :key="plan.id"
              @click="selectPropertyPlan(plan)"
              class="group flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition"
              :style="selectedPlan?.id === plan.id ? 'background: var(--mint); color: #080C0B' : 'background: transparent; color: var(--text-muted)'"
            >
              <p class="text-xs truncate" :style="selectedPlan?.id === plan.id ? 'color: #080C0B' : 'color: var(--text)'">{{ plan.title }}</p>
              <button @click.stop="deletePropertyPlan(plan.id)" class="opacity-0 group-hover:opacity-80 transition-opacity" :style="selectedPlan?.id === plan.id ? 'color: #080C0B' : 'color: var(--text-muted)'">
                <i class="pi pi-trash text-[10px]"></i>
              </button>
            </div>
          </div>
        </aside>

        <div class="lg:col-span-6 rounded-xl border flex flex-col" style="border-color: var(--border); min-height: 380px">
          <div class="px-3 py-2 border-b" style="border-color: var(--border)">
            <p class="text-xs" style="color: var(--text)">{{ selectedPlan ? selectedPlan.title : 'Select a plan' }}</p>
          </div>

          <div v-if="!selectedPlan" class="flex-1 flex items-center justify-center px-6">
            <p class="text-xs text-center" style="color: var(--text-muted)">Pick a plan on the left to chat, or create one for this property.</p>
          </div>

          <template v-else>
            <div ref="planMessagesEl" class="flex-1 overflow-y-auto px-3 py-3 space-y-3">
              <div v-if="loadingPlanMessages" class="text-xs text-center py-6" style="color: var(--text-muted)">Loading conversation…</div>

              <div v-else-if="planMessages.length === 0" class="space-y-2">
                <button
                  v-for="prompt in ['Build a 12-month plan to increase this property\'s cash flow', 'What should I prioritize over the next 30 days for this property?']"
                  :key="prompt"
                  @click="sendPlanMessage(prompt)"
                  :disabled="streamingPlan"
                  class="w-full text-left text-xs rounded-lg border px-3 py-2 hover:opacity-80 disabled:opacity-50"
                  style="border-color: var(--border); color: var(--text-muted); background: var(--surface-2)"
                >
                  {{ prompt }}
                </button>
              </div>

              <div v-else v-for="(msg, i) in planMessages" :key="i" :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']">
                <div class="max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed"
                  :style="msg.role === 'user' ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text); border: 1px solid var(--border)'">
                  <pre class="whitespace-pre-wrap font-sans text-xs leading-relaxed">{{ msg.content }}<span v-if="msg.streaming" class="inline-block w-0.5 h-3 ml-0.5 align-text-bottom animate-pulse" style="background: currentColor"></span></pre>
                </div>
              </div>
            </div>

            <div class="px-3 py-2 border-t" style="border-color: var(--border)">
              <div class="flex items-end gap-2">
                <Textarea
                  v-model="planInputText"
                  @keydown.enter.exact.prevent="sendPlan"
                  :autoResize="true"
                  rows="1"
                  class="flex-1 text-xs"
                  placeholder="Ask about this property plan, or say: add todo: call lender"
                  :disabled="streamingPlan"
                />
                <Button icon="pi pi-send" class="p-button-primary" size="small" :loading="streamingPlan" :disabled="!planInputText.trim() || streamingPlan" @click="sendPlan" />
              </div>
            </div>
          </template>
        </div>

        <aside class="lg:col-span-3 rounded-xl border p-3" style="border-color: var(--border); background: var(--surface-2)">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs font-semibold" style="color: var(--text)">Todo</p>
            <span v-if="selectedPlan" class="text-[10px] px-1.5 py-0.5 rounded" style="background: rgba(61,219,184,0.15); color: var(--mint)">{{ todos.filter(t => !t.done).length }} open</span>
          </div>

          <div v-if="!selectedPlan" class="text-xs py-6 text-center" style="color: var(--text-muted)">Select a plan to manage todos.</div>

          <template v-else>
            <div class="flex gap-2 mb-3">
              <InputText v-model="todoInput" class="w-full" placeholder="Add a todo" @keydown.enter="addTodo" />
              <Button icon="pi pi-plus" size="small" class="p-button-primary" :loading="addingTodo" :disabled="!todoInput.trim() || addingTodo" @click="addTodo" />
            </div>

            <div v-if="loadingTodos" class="text-xs text-center py-4" style="color: var(--text-muted)">Loading todos…</div>
            <div v-else-if="todos.length === 0" class="text-xs text-center py-4" style="color: var(--text-muted)">No todos yet.</div>
            <div v-else class="space-y-1.5 max-h-80 overflow-y-auto pr-0.5">
              <div v-for="todo in todos" :key="todo.id" class="flex items-start gap-2 px-2 py-1.5 rounded-lg" style="background: var(--surface)">
                <input type="checkbox" class="mt-0.5" :checked="todo.done" @change="toggleTodo(todo)" />
                <p class="text-xs flex-1" :style="todo.done ? 'color: var(--text-muted); text-decoration: line-through' : 'color: var(--text)'">#{{ todo.id }} {{ todo.content }}</p>
                <button @click="deleteTodo(todo.id)" style="color: var(--text-muted)" class="hover:opacity-80">
                  <i class="pi pi-trash text-[10px]"></i>
                </button>
              </div>
            </div>

            <p class="text-[10px] mt-3" style="color: var(--text-muted)">In chat, try: "add todo: compare refinance options" or "complete todo #12".</p>
          </template>
        </aside>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-2 mb-5">
      <button v-for="t in ['transactions','documents']" :key="t" @click="tab = t"
        class="px-4 py-2 rounded-lg text-sm font-medium transition capitalize"
        :style="tab === t ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">
        {{ t }}
      </button>
    </div>

    <!-- Transactions tab -->
    <div v-if="tab === 'transactions'">
      <div class="flex justify-between items-center mb-4">
        <div class="flex gap-2">
          <button v-for="f in ['all','income','expense']" :key="f" @click="txnFilter = f; loadTxns()"
            class="px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition"
            :style="txnFilter === f ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">
            {{ f }}
          </button>
        </div>
        <Button @click="showAddTxn = true" label="Add" icon="pi pi-plus" class="p-button-primary" size="small" />
      </div>

      <!-- Summary -->
      <div v-if="txnSummary" class="grid grid-cols-3 gap-3 mb-4">
        <div class="rounded-lg p-3 text-center" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Income</p>
          <p class="font-bold text-sm mt-0.5" style="color: var(--mint)">${{ fmt(txnSummary.income) }}</p>
        </div>
        <div class="rounded-lg p-3 text-center" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Expenses</p>
          <p class="font-bold text-sm mt-0.5" style="color: #f87171">${{ fmt(txnSummary.expenses) }}</p>
        </div>
        <div class="rounded-lg p-3 text-center" style="background: var(--surface-2)">
          <p class="text-xs" style="color: var(--text-muted)">Net</p>
          <p class="font-bold text-sm mt-0.5" :style="txnSummary.net >= 0 ? 'color: var(--mint)' : 'color: #f87171'">${{ fmt(txnSummary.net) }}</p>
        </div>
      </div>

      <div v-if="transactions.length === 0" class="rounded-xl border p-8 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
        <p class="text-sm" style="color: var(--text-muted)">No transactions yet</p>
      </div>
      <div v-else class="rounded-xl border overflow-hidden" style="background: var(--surface); border-color: var(--border)">
        <div v-for="(txn, i) in transactions" :key="txn.id"
          class="flex items-center gap-4 px-4 py-3 border-b last:border-0"
          :style="i % 2 !== 0 ? 'background: var(--surface-2); border-color: var(--border)' : 'border-color: var(--border)'">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            :style="txn.type === 'income' ? 'background: rgba(61,219,184,0.15)' : 'background: rgba(248,113,113,0.15)'">
            <i :class="`pi ${txn.type === 'income' ? 'pi-arrow-down-left' : 'pi-arrow-up-right'} text-sm`"
              :style="txn.type === 'income' ? 'color: var(--mint)' : 'color: #f87171'"></i>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm" style="color: var(--text)">{{ txn.description || txn.category || txn.type }}</p>
            <p class="text-xs" style="color: var(--text-muted)">{{ txn.date }}</p>
          </div>
          <p class="font-semibold text-sm" :style="txn.type === 'income' ? 'color: var(--mint)' : 'color: #f87171'">
            {{ txn.type === 'income' ? '+' : '-' }}${{ fmt(txn.amount) }}
          </p>
          <button @click="deleteTxn(txn.id)" style="color: var(--text-muted)" class="hover:opacity-80">
            <i class="pi pi-trash text-xs"></i>
          </button>
        </div>
      </div>
    </div>

    <!-- Documents tab -->
    <div v-if="tab === 'documents'">
      <div class="flex justify-between items-center mb-4">
        <p class="text-sm" style="color: var(--text-muted)">{{ docs.length }} document{{ docs.length !== 1 ? 's' : '' }}</p>
        <label class="cursor-pointer">
          <input type="file" class="hidden" @change="uploadFile" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" />
          <span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium cursor-pointer" style="background: var(--mint); color: #080C0B">
            <i class="pi pi-upload"></i> Upload
          </span>
        </label>
      </div>
      <div v-if="uploadProgress > 0 && uploadProgress < 100" class="mb-4 h-1.5 rounded-full overflow-hidden" style="background: var(--surface-2)">
        <div class="h-full rounded-full transition-all" :style="`width: ${uploadProgress}%; background: var(--mint)`"></div>
      </div>
      <div v-if="docs.length === 0" class="rounded-xl border p-8 text-center" style="background: var(--surface); border-color: var(--border); border-style: dashed">
        <i class="pi pi-file text-2xl mb-2" style="color: var(--mint)"></i>
        <p class="text-sm" style="color: var(--text-muted)">No documents uploaded</p>
      </div>
      <div v-else class="space-y-2">
        <div v-for="doc in docs" :key="doc.id" class="flex items-center gap-3 p-3 rounded-lg" style="background: var(--surface); border: 1px solid var(--border)">
          <i class="pi pi-file-pdf text-lg" style="color: var(--mint)"></i>
          <div class="flex-1 min-w-0">
            <p class="text-sm truncate" style="color: var(--text)">{{ doc.name }}</p>
            <p class="text-xs" style="color: var(--text-muted)">{{ fmtBytes(doc.size_bytes) }} · {{ doc.uploaded_at.slice(0,10) }}</p>
          </div>
          <button @click="downloadDoc(doc)" title="Download" style="color: var(--mint)" class="hover:opacity-80"><i class="pi pi-download"></i></button>
          <button @click="deleteDoc(doc.id)" style="color: var(--text-muted)" class="hover:opacity-80"><i class="pi pi-trash text-xs"></i></button>
        </div>
      </div>
    </div>

    <!-- Import result dialog -->
    <Dialog v-model:visible="showCsvResult" :header="csvResult?.source === 'json' ? 'JSON Import Complete' : 'CSV Import Complete'" modal :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '380px' }">
      <div class="py-3 space-y-3" v-if="csvResult">

        <!-- JSON result -->
        <template v-if="csvResult.source === 'json'">
          <div class="space-y-2">
            <div v-for="row in csvResult.displayRows" :key="row.label" class="flex justify-between items-center py-1.5 border-b" style="border-color: var(--border)">
              <span class="text-xs" style="color: var(--text-muted)">{{ row.label }}</span>
              <span class="text-sm font-medium" style="color: var(--text)">{{ row.value }}</span>
            </div>
          </div>
          <p class="text-xs" style="color: var(--text-muted)">Balance, rate, and monthly payment updated from your servicer export.</p>
        </template>

        <!-- CSV result -->
        <template v-else>
          <div class="grid grid-cols-3 gap-2 text-center">
            <div class="rounded-lg p-3" style="background: var(--surface-2)">
              <p class="text-lg font-bold" style="color: var(--mint)">{{ csvResult.rows_parsed }}</p>
              <p class="text-xs mt-0.5" style="color: var(--text-muted)">Rows parsed</p>
            </div>
            <div class="rounded-lg p-3" style="background: var(--surface-2)">
              <p class="text-lg font-bold" style="color: var(--mint)">{{ csvResult.imported }}</p>
              <p class="text-xs mt-0.5" style="color: var(--text-muted)">Imported</p>
            </div>
            <div class="rounded-lg p-3" style="background: var(--surface-2)">
              <p class="text-lg font-bold" style="color: var(--text)">{{ csvResult.skipped }}</p>
              <p class="text-xs mt-0.5" style="color: var(--text-muted)">Skipped</p>
            </div>
          </div>
          <p class="text-xs" style="color: var(--text-muted)">Balance, rate, and payment updated from the most recent row. Payment transactions added to history (duplicates skipped).</p>
        </template>

      </div>
      <template #footer>
        <Button @click="showCsvResult = false" label="Done" class="p-button-primary" />
      </template>
    </Dialog>

    <!-- Import format helper dialog -->
    <Dialog v-model:visible="showCsvHelp" header="Import Format" modal :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '460px' }">
      <div class="py-3 space-y-4">

        <div>
          <p class="text-xs font-semibold mb-2" style="color: var(--text)">JSON — Servicer API export (e.g. Newrez)</p>
          <p class="text-xs mb-2" style="color: var(--text-muted)">Download the JSON response from your lender's portal or API. Recognized fields:</p>
          <div class="rounded-lg p-3 text-xs font-mono overflow-x-auto whitespace-pre" style="background: var(--surface-2); color: var(--text)">PrincipalBalance, InterestRate, MonthlyPayment
TotalPayment, PIPayment, EscrowPayment, LoanId</div>
          <p class="text-xs mt-1.5" style="color: var(--text-muted)">camelCase and snake_case variants are also recognized automatically.</p>
        </div>

        <div class="border-t pt-3" style="border-color: var(--border)">
          <p class="text-xs font-semibold mb-2" style="color: var(--text)">CSV — Statement history</p>
          <p class="text-xs mb-2" style="color: var(--text-muted)">One row per payment period. Recognized columns (extra columns ignored):</p>
          <div class="rounded-lg p-3 text-xs font-mono overflow-x-auto whitespace-pre" style="background: var(--surface-2); color: var(--text)">date,balance,payment,principal,interest,rate
2024-01-15,245000.00,1850.00,852.50,997.50,6.5
2024-02-15,244147.50,1850.00,856.00,994.00,6.5</div>
          <p class="text-xs mt-1.5" style="color: var(--text-muted)">Column name aliases like <span style="color:var(--mint)">principal_balance</span>, <span style="color:var(--mint)">total_payment</span>, <span style="color:var(--mint)">interest_rate</span> are accepted. $ and , in numbers are ignored.</p>
        </div>

      </div>
      <template #footer>
        <Button @click="showCsvHelp = false" label="Got it" class="p-button-primary" />
      </template>
    </Dialog>

    <!-- Link Mortgage dialog -->
    <Dialog v-model:visible="showLinkMortgage" header="Link Mortgage Account" modal :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '400px' }">
      <div class="py-2">
        <p class="text-xs mb-4" style="color: var(--text-muted)">Select a connected loan account to sync mortgage data automatically. If your lender isn't listed, connect it first via the Accounts tab.</p>
        <div v-if="loadingLoanAccounts" class="text-sm text-center py-4" style="color: var(--text-muted)">Loading…</div>
        <div v-else-if="loanAccounts.length === 0" class="rounded-lg p-4 text-center" style="background: var(--surface-2)">
          <i class="pi pi-building-columns text-2xl mb-2" style="color: var(--mint)"></i>
          <p class="text-sm" style="color: var(--text)">No loan accounts found</p>
          <p class="text-xs mt-1" style="color: var(--text-muted)">Go to Accounts and link your mortgage lender via Plaid</p>
        </div>
        <div v-else class="space-y-2">
          <label v-for="acct in loanAccounts" :key="acct.account_id"
            class="flex items-center gap-3 p-3 rounded-lg cursor-pointer transition"
            :style="selectedLoanAccount === acct.account_id ? 'background: rgba(61,219,184,0.12); border: 1px solid var(--mint)' : 'background: var(--surface-2); border: 1px solid transparent'">
            <input type="radio" :value="acct.account_id" v-model="selectedLoanAccount" class="hidden" />
            <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style="background: var(--surface)">
              <i class="pi pi-percentage text-sm" style="color: var(--mint)"></i>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium" style="color: var(--text)">{{ acct.institution_name }}</p>
              <p class="text-xs" style="color: var(--text-muted)">{{ acct.name }} · ••••{{ acct.mask }}</p>
            </div>
            <p class="text-sm font-semibold" style="color: var(--text)">${{ fmt(acct.current_balance) }}</p>
          </label>
        </div>
      </div>
      <template #footer>
        <Button @click="showLinkMortgage = false" label="Cancel" severity="secondary" text />
        <Button @click="linkMortgage" label="Link & Sync" class="p-button-primary" :loading="linking" :disabled="!selectedLoanAccount" />
      </template>
    </Dialog>

    <!-- Add transaction dialog -->
    <Dialog v-model:visible="showAddTxn" header="Add Transaction" modal :style="{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text)', width: '360px' }">
      <div class="space-y-3 py-2">
        <div class="flex gap-2">
          <button v-for="t in ['income','expense']" :key="t" @click="txnForm.type = t"
            class="flex-1 py-2 rounded-lg text-sm font-medium capitalize transition"
            :style="txnForm.type === t ? 'background: var(--mint); color: #080C0B' : 'background: var(--surface-2); color: var(--text-muted)'">
            {{ t }}
          </button>
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Amount ($)</label>
          <InputText v-model="txnForm.amount" type="number" step="0.01" min="0.01" class="w-full" placeholder="0.00" />
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Date</label>
          <InputText v-model="txnForm.date" type="date" class="w-full" />
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Description</label>
          <InputText v-model="txnForm.description" class="w-full" placeholder="Rent payment, repair, etc." />
        </div>
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted)">Category</label>
          <select v-model="txnForm.category" class="w-full px-3 py-2 rounded-lg text-sm" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text)">
            <option value="">None</option>
            <option value="rent">Rent</option>
            <option value="mortgage">Mortgage Payment</option>
            <option value="improvement">Improvement</option>
            <option value="maintenance">Maintenance</option>
            <option value="insurance">Insurance</option>
            <option value="taxes">Property Taxes</option>
            <option value="utilities">Utilities</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>
      <template #footer>
        <Button @click="showAddTxn = false" label="Cancel" severity="secondary" text />
        <Button @click="addTxn" label="Add" class="p-button-primary" :loading="savingTxn" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import api from '@/utils/api'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend)

const route = useRoute()
const propertyId = route.params.id

const property = ref(null)
const analytics = ref(null)
const loadingAnalytics = ref(true)
const applyingEstimate = ref(false)
const enrichingAddress = ref(false)
const enrichStatus = ref('')
const editingCurrentValue = ref(false)
const currentValueDraft = ref('')
const savingCurrentValue = ref(false)
const currentValueStatus = ref('')
const additionalPrincipalPayment = ref(0)
const lumpSumPayment = ref(0)
const projectionInterestRate = ref('')
const projectionMonths = ref(120)
const historyMonths = ref(24)
const transactions = ref([])
const txnSummary = ref(null)
const docs = ref([])
const tab = ref('transactions')
const txnFilter = ref('all')
const showAddTxn = ref(false)
const savingTxn = ref(false)
const uploadProgress = ref(0)
const txnForm = ref({ type: 'income', amount: '', date: new Date().toISOString().slice(0,10), description: '', category: '' })

// Mortgage linking & CSV import
const showLinkMortgage = ref(false)
const loanAccounts = ref([])
const loadingLoanAccounts = ref(false)
const selectedLoanAccount = ref(null)
const linking = ref(false)
const syncing = ref(false)
const importingCsv = ref(false)
const showCsvResult = ref(false)
const showCsvHelp = ref(false)
const csvResult = ref(null)

// Property-scoped planning
const propertyPlans = ref([])
const loadingPropertyPlans = ref(false)
const selectedPlan = ref(null)
const planMessages = ref([])
const loadingPlanMessages = ref(false)
const planInputText = ref('')
const streamingPlan = ref(false)
const planMessagesEl = ref(null)
const showNewPlanComposer = ref(false)
const creatingPropertyPlan = ref(false)
const newPlanTitle = ref('')

// Plan todos
const todos = ref([])
const loadingTodos = ref(false)
const todoInput = ref('')
const addingTodo = ref(false)

const linkedAccountLabel = computed(() => {
  const acct = loanAccounts.value.find(a => a.account_id === property.value?.mortgage_account_id)
  if (!acct) return property.value?.mortgage_account_id ? 'Synced via Plaid' : ''
  return `${acct.institution_name} ••••${acct.mask}`
})

const hasManualCurrentValue = computed(() => property.value?.current_value != null)
const displayCurrentValue = computed(() => {
  if (property.value?.current_value != null) return property.value.current_value
  return analytics.value?.current?.effective_current_value ?? null
})
const displayEquity = computed(() => {
  if (property.value?.current_value != null && property.value?.mortgage_balance != null) {
    return Number(property.value.current_value || 0) - Number(property.value.mortgage_balance || 0)
  }
  return analytics.value?.current?.equity ?? property.value?.equity ?? null
})

const fmtMonthLabel = (monthOffset) => {
  const d = new Date()
  d.setDate(1)
  d.setMonth(d.getMonth() + monthOffset)
  return d.toLocaleString('en-US', { month: 'short', year: '2-digit' })
}

const buildInterestSchedule = ({
  startingBalance,
  annualRatePct,
  monthlyPayment,
  additionalPayment,
  lumpSumPayment,
  monthsToProject,
}) => {
  const labels = Array.from({ length: monthsToProject }, (_, i) => fmtMonthLabel(i))
  const cumulativeInterest = []
  const balanceSeries = []
  const principalShareSeries = []
  const interestShareSeries = []

  let balance = startingBalance
  let totalInterest = 0
  let payoffMonth = null

  const oneTimePrincipal = Math.max(Number(lumpSumPayment) || 0, 0)
  if (oneTimePrincipal > 0) {
    balance = Math.max(balance - oneTimePrincipal, 0)
  }

  if (balance <= 0) {
    for (let month = 1; month <= monthsToProject; month += 1) {
      cumulativeInterest.push(0)
      balanceSeries.push(0)
      principalShareSeries.push(0)
      interestShareSeries.push(0)
    }
    return {
      labels,
      cumulativeInterest,
      balanceSeries,
      principalShareSeries,
      interestShareSeries,
      totalInterestProjected: 0,
      payoffMonth: 0,
    }
  }

  if (annualRatePct <= 0) {
    const totalMonthlyPayment = monthlyPayment + additionalPayment
    if (totalMonthlyPayment <= 0) {
      return {
        labels,
        cumulativeInterest: [],
        balanceSeries: [],
        principalShareSeries: [],
        interestShareSeries: [],
        totalInterestProjected: 0,
        payoffMonth: null,
      }
    }

    for (let month = 1; month <= monthsToProject; month += 1) {
      if (balance <= 0) {
        cumulativeInterest.push(totalInterest)
        balanceSeries.push(0)
        principalShareSeries.push(0)
        interestShareSeries.push(0)
        if (payoffMonth == null) payoffMonth = month - 1
        continue
      }

      const principalForMonth = Math.min(totalMonthlyPayment, balance)
      const paymentApplied = principalForMonth

      balance = Math.max(balance - principalForMonth, 0)
      cumulativeInterest.push(totalInterest)
      balanceSeries.push(balance)
      principalShareSeries.push(paymentApplied > 0 ? 100 : 0)
      interestShareSeries.push(paymentApplied > 0 ? 0 : 0)
      if (balance <= 0 && payoffMonth == null) payoffMonth = month
    }

    return {
      labels,
      cumulativeInterest,
      balanceSeries,
      principalShareSeries,
      interestShareSeries,
      totalInterestProjected: cumulativeInterest.at(-1) ?? 0,
      payoffMonth,
    }
  }

  const monthlyRate = annualRatePct / 100 / 12
  const totalMonthlyPayment = monthlyPayment + additionalPayment

  if (totalMonthlyPayment <= balance * monthlyRate) {
    return {
      labels,
      cumulativeInterest: [],
      totalInterestProjected: 0,
      payoffMonth: null,
      error: 'Monthly payment is too low to amortize this loan at the current rate. Increase payment or adjust loan terms.',
    }
  }

  for (let month = 1; month <= monthsToProject; month += 1) {
    if (balance <= 0) {
      cumulativeInterest.push(totalInterest)
      balanceSeries.push(0)
      principalShareSeries.push(0)
      interestShareSeries.push(0)
      if (payoffMonth == null) payoffMonth = month - 1
      continue
    }

    const interestForMonth = balance * monthlyRate
    let principalForMonth = totalMonthlyPayment - interestForMonth
    if (principalForMonth > balance) principalForMonth = balance
    const paymentApplied = principalForMonth + interestForMonth

    totalInterest += interestForMonth
    balance = Math.max(balance - principalForMonth, 0)
    cumulativeInterest.push(totalInterest)
    balanceSeries.push(balance)
    principalShareSeries.push(paymentApplied > 0 ? (principalForMonth / paymentApplied) * 100 : 0)
    interestShareSeries.push(paymentApplied > 0 ? (interestForMonth / paymentApplied) * 100 : 0)

    if (balance <= 0 && payoffMonth == null) payoffMonth = month
  }

  return {
    labels,
    cumulativeInterest,
    balanceSeries,
    principalShareSeries,
    interestShareSeries,
    totalInterestProjected: cumulativeInterest.at(-1) ?? 0,
    payoffMonth,
  }
}

const interestProjection = computed(() => {
  const balance = Number(property.value?.mortgage_balance)
  const rate = Number(projectionInterestRate.value)
  const payment = Number(property.value?.mortgage_payment)
  const extraPayment = Math.max(Number(additionalPrincipalPayment.value) || 0, 0)
  const lumpSum = Math.max(Number(lumpSumPayment.value) || 0, 0)

  if (!Number.isFinite(balance) || balance <= 0) {
    return { error: 'Add a mortgage balance to project interest.', baseline: null, withExtra: null, labels: [] }
  }
  if (!Number.isFinite(rate) || rate < 0) {
    return { error: 'Add a valid interest rate (%) in the top row to project interest.', baseline: null, withExtra: null, labels: [] }
  }
  if (!Number.isFinite(payment) || payment <= 0) {
    return { error: 'Add a valid monthly payment to project interest.', baseline: null, withExtra: null, labels: [] }
  }

  const baseline = buildInterestSchedule({
    startingBalance: balance,
    annualRatePct: rate,
    monthlyPayment: payment,
    additionalPayment: 0,
    lumpSumPayment: 0,
    monthsToProject: projectionMonths.value,
  })
  if (baseline.error) {
    return { error: baseline.error, baseline: null, withExtra: null, labels: [] }
  }

  const withExtra = buildInterestSchedule({
    startingBalance: balance,
    annualRatePct: rate,
    monthlyPayment: payment,
    additionalPayment: extraPayment,
    lumpSumPayment: lumpSum,
    monthsToProject: projectionMonths.value,
  })
  if (withExtra.error) {
    return { error: withExtra.error, baseline: null, withExtra: null, labels: [] }
  }

  return {
    error: null,
    labels: baseline.labels,
    baseline,
    withExtra,
  }
})

const projectedInterestSavings = computed(() => {
  if (interestProjection.value.error || !interestProjection.value.baseline || !interestProjection.value.withExtra) return 0
  return Math.max(
    Number(interestProjection.value.baseline.totalInterestProjected || 0) - Number(interestProjection.value.withExtra.totalInterestProjected || 0),
    0,
  )
})

const paymentMixSummary = computed(() => {
  if (interestProjection.value.error || !interestProjection.value.baseline || !interestProjection.value.withExtra) {
    return {
      baselinePrincipalPct: 0,
      baselineInterestPct: 0,
      withExtraPrincipalPct: 0,
      withExtraInterestPct: 0,
    }
  }

  return {
    baselinePrincipalPct: Number(interestProjection.value.baseline.principalShareSeries?.[0] || 0),
    baselineInterestPct: Number(interestProjection.value.baseline.interestShareSeries?.[0] || 0),
    withExtraPrincipalPct: Number(interestProjection.value.withExtra.principalShareSeries?.[0] || 0),
    withExtraInterestPct: Number(interestProjection.value.withExtra.interestShareSeries?.[0] || 0),
  }
})

const payoffLabel = (monthCount) => {
  if (monthCount == null) return `>${projectionMonths.value} months`
  if (monthCount <= 0) return 'Paid off'
  const years = Math.floor(monthCount / 12)
  const months = monthCount % 12
  if (years === 0) return `${months} mo`
  if (months === 0) return `${years} yr`
  return `${years} yr ${months} mo`
}

const projectionAnnualGrowthRate = computed(() => {
  const raw = Number(analytics.value?.assumptions?.market_annual_growth)
  if (Number.isFinite(raw) && raw >= 0) return raw
  return 0.03
})

const projectedEquityCurve = computed(() => {
  if (interestProjection.value.error || !interestProjection.value.withExtra) return []

  const basePropertyValue = Number(displayCurrentValue.value)
  if (!Number.isFinite(basePropertyValue) || basePropertyValue <= 0) return []

  const monthlyGrowth = projectionAnnualGrowthRate.value / 12
  const balances = interestProjection.value.withExtra.balanceSeries || []
  return balances.map((balance, idx) => {
    const projectedValue = basePropertyValue * ((1 + monthlyGrowth) ** (idx + 1))
    return Math.max(projectedValue - Number(balance || 0), 0)
  })
})

const interestProjectionChartData = computed(() => {
  if (interestProjection.value.error) return { labels: [], datasets: [] }

  const datasets = [
    {
      label: 'Cumulative Interest (Current Payment)',
      data: interestProjection.value.baseline?.cumulativeInterest || [],
      borderColor: '#f87171',
      backgroundColor: 'rgba(248,113,113,0.15)',
      pointRadius: 0,
      tension: 0.25,
    },
    {
      label: 'Cumulative Interest (With Extra Payment)',
      data: interestProjection.value.withExtra?.cumulativeInterest || [],
      borderColor: '#3DDBB8',
      backgroundColor: 'rgba(61,219,184,0.15)',
      pointRadius: 0,
      tension: 0.25,
    },
  ]

  if (projectedEquityCurve.value.length) {
    datasets.push({
      label: 'Projected Equity (With Extra Plan)',
      data: projectedEquityCurve.value,
      borderColor: '#60a5fa',
      backgroundColor: 'rgba(96,165,250,0.14)',
      pointRadius: 0,
      tension: 0.25,
      yAxisID: 'y1',
    })
  }

  return {
    labels: interestProjection.value.labels,
    datasets,
  }
})

const paymentMixChartData = computed(() => {
  if (interestProjection.value.error) return { labels: [], datasets: [] }
  return {
    labels: interestProjection.value.labels,
    datasets: [
      {
        label: 'Principal % (Current)',
        data: interestProjection.value.baseline?.principalShareSeries || [],
        borderColor: '#22c55e',
        backgroundColor: 'rgba(34,197,94,0.12)',
        pointRadius: 0,
        tension: 0.25,
      },
      {
        label: 'Interest % (Current)',
        data: interestProjection.value.baseline?.interestShareSeries || [],
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.12)',
        pointRadius: 0,
        tension: 0.25,
      },
      {
        label: 'Principal % (Extra Plan)',
        data: interestProjection.value.withExtra?.principalShareSeries || [],
        borderColor: '#3DDBB8',
        backgroundColor: 'rgba(61,219,184,0.12)',
        borderDash: [6, 4],
        pointRadius: 0,
        tension: 0.25,
      },
      {
        label: 'Interest % (Extra Plan)',
        data: interestProjection.value.withExtra?.interestShareSeries || [],
        borderColor: '#f97316',
        backgroundColor: 'rgba(249,115,22,0.12)',
        borderDash: [6, 4],
        pointRadius: 0,
        tension: 0.25,
      },
    ],
  }
})

const startEditCurrentValue = () => {
  const startingValue = property.value?.current_value ?? analytics.value?.current?.effective_current_value ?? ''
  currentValueDraft.value = startingValue === '' ? '' : String(startingValue)
  currentValueStatus.value = ''
  editingCurrentValue.value = true
}

const cancelEditCurrentValue = () => {
  editingCurrentValue.value = false
  currentValueDraft.value = ''
  currentValueStatus.value = ''
}

const debtEquityChartData = computed(() => {
  const points = analytics.value?.history || []
  return {
    labels: points.map(p => p.month),
    datasets: [
      {
        label: 'Debt',
        data: points.map(p => p.debt),
        borderColor: '#f87171',
        backgroundColor: 'rgba(248,113,113,0.2)',
        pointRadius: 2,
        tension: 0.25,
      },
      {
        label: 'Equity',
        data: points.map(p => p.equity),
        borderColor: '#3DDBB8',
        backgroundColor: 'rgba(61,219,184,0.18)',
        pointRadius: 2,
        tension: 0.25,
      },
    ],
  }
})

const lineChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#94A3B8', boxWidth: 10, boxHeight: 10 },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: $${Number(ctx.parsed.y || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`,
      },
    },
  },
  scales: {
    x: {
      ticks: { color: '#94A3B8' },
      grid: { display: false },
    },
    y: {
      ticks: {
        color: '#94A3B8',
        callback: (value) => `$${Number(value).toLocaleString('en-US')}`,
      },
      grid: { color: 'rgba(148,163,184,0.15)' },
    },
    y1: {
      position: 'right',
      ticks: {
        color: '#94A3B8',
        callback: (value) => `$${Number(value).toLocaleString('en-US')}`,
      },
      grid: { display: false },
    },
  },
}))

const interestProjectionChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#94A3B8', boxWidth: 10, boxHeight: 10 },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: $${Number(ctx.parsed.y || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}`,
      },
    },
  },
  scales: {
    x: {
      ticks: {
        color: '#94A3B8',
        maxTicksLimit: 10,
      },
      grid: { display: false },
    },
    y: {
      ticks: {
        color: '#94A3B8',
        callback: (value) => `$${Number(value).toLocaleString('en-US')}`,
      },
      grid: { color: 'rgba(148,163,184,0.15)' },
    },
  },
}))

const paymentMixChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#94A3B8', boxWidth: 10, boxHeight: 10 },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.y || 0).toFixed(1)}%`,
      },
    },
  },
  scales: {
    x: {
      ticks: {
        color: '#94A3B8',
        maxTicksLimit: 10,
      },
      grid: { display: false },
    },
    y: {
      min: 0,
      max: 100,
      ticks: {
        color: '#94A3B8',
        callback: (value) => `${Number(value).toFixed(0)}%`,
      },
      grid: { color: 'rgba(148,163,184,0.15)' },
    },
  },
}))

const fmt = (v) => v != null ? Number(v).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : '—'
const fmtPct = (v) => `${Number(v || 0).toFixed(1)}%`
const fmtBytes = (b) => b > 1048576 ? `${(b/1048576).toFixed(1)} MB` : `${(b/1024).toFixed(0)} KB`

const scrollPlanMessagesToBottom = () => {
  nextTick(() => {
    if (planMessagesEl.value) {
      planMessagesEl.value.scrollTop = planMessagesEl.value.scrollHeight
    }
  })
}

const loadPropertyPlans = async () => {
  loadingPropertyPlans.value = true
  try {
    const res = await api.get(`/api/plans?property_id=${propertyId}`)
    propertyPlans.value = res.data
  } finally {
    loadingPropertyPlans.value = false
  }
}

const loadTodos = async () => {
  if (!selectedPlan.value) {
    todos.value = []
    return
  }
  loadingTodos.value = true
  try {
    const res = await api.get(`/api/plans/${selectedPlan.value.id}/todos`)
    todos.value = res.data
  } finally {
    loadingTodos.value = false
  }
}

const selectPropertyPlan = async (plan) => {
  if (selectedPlan.value?.id === plan.id) return
  selectedPlan.value = plan
  planMessages.value = []
  loadingPlanMessages.value = true
  try {
    const res = await api.get(`/api/plans/${plan.id}/messages`)
    planMessages.value = res.data
    await loadTodos()
    scrollPlanMessagesToBottom()
  } finally {
    loadingPlanMessages.value = false
  }
}

const createPropertyPlan = async () => {
  const title = newPlanTitle.value.trim()
  if (!title || creatingPropertyPlan.value) return
  creatingPropertyPlan.value = true
  try {
    const res = await api.post('/api/plans', { title, property_id: Number(propertyId) })
    propertyPlans.value.unshift(res.data)
    newPlanTitle.value = ''
    showNewPlanComposer.value = false
    await selectPropertyPlan(res.data)
  } finally {
    creatingPropertyPlan.value = false
  }
}

const deletePropertyPlan = async (id) => {
  if (!confirm('Delete this plan and all related todos/messages?')) return
  await api.delete(`/api/plans/${id}`)
  propertyPlans.value = propertyPlans.value.filter(p => p.id !== id)
  if (selectedPlan.value?.id === id) {
    selectedPlan.value = null
    planMessages.value = []
    todos.value = []
  }
}

const sendPlan = () => {
  const text = planInputText.value.trim()
  if (!text || !selectedPlan.value || streamingPlan.value) return
  planInputText.value = ''
  sendPlanMessage(text)
}

const sendPlanMessage = async (text) => {
  if (streamingPlan.value || !selectedPlan.value) return
  planMessages.value.push({ role: 'user', content: text })
  scrollPlanMessagesToBottom()

  const assistantIdx = planMessages.value.length
  planMessages.value.push({ role: 'assistant', content: '', streaming: true })
  streamingPlan.value = true

  try {
    const baseUrl = api.defaults.baseURL || ''
    const token = window.localStorage.getItem('access_token')

    const response = await fetch(`${baseUrl}/api/plans/${selectedPlan.value.id}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ content: text }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6).trim()
        if (payload === '[DONE]') break
        try {
          const { text: tokenChunk, error } = JSON.parse(payload)
          if (error) {
            planMessages.value[assistantIdx].content = `Error: ${error}`
          } else if (tokenChunk) {
            planMessages.value[assistantIdx].content += tokenChunk
            scrollPlanMessagesToBottom()
          }
        } catch {}
      }
    }
  } catch {
    planMessages.value[assistantIdx].content = 'Something went wrong. Please try again.'
  } finally {
    if (planMessages.value[assistantIdx]) {
      planMessages.value[assistantIdx].streaming = false
    }
    streamingPlan.value = false
    scrollPlanMessagesToBottom()
    await loadTodos()
  }
}

const addTodo = async () => {
  const content = todoInput.value.trim()
  if (!content || !selectedPlan.value || addingTodo.value) return
  addingTodo.value = true
  try {
    const res = await api.post(`/api/plans/${selectedPlan.value.id}/todos`, { content })
    todoInput.value = ''
    todos.value.push(res.data)
    todos.value.sort((a, b) => (a.done - b.done) || (a.position - b.position) || (a.id - b.id))
  } finally {
    addingTodo.value = false
  }
}

const toggleTodo = async (todo) => {
  if (!selectedPlan.value) return
  const original = todo.done
  todo.done = !todo.done
  try {
    await api.put(`/api/plans/${selectedPlan.value.id}/todos/${todo.id}`, { done: todo.done })
    todos.value.sort((a, b) => (a.done - b.done) || (a.position - b.position) || (a.id - b.id))
  } catch {
    todo.done = original
  }
}

const deleteTodo = async (todoId) => {
  if (!selectedPlan.value) return
  await api.delete(`/api/plans/${selectedPlan.value.id}/todos/${todoId}`)
  todos.value = todos.value.filter(t => t.id !== todoId)
}

const loadProperty = async () => {
  const res = await api.get(`/api/properties/${propertyId}`)
  property.value = res.data
}

const loadAnalytics = async () => {
  loadingAnalytics.value = true
  try {
    const res = await api.get(`/api/properties/${propertyId}/analytics?months=${historyMonths.value}`)
    analytics.value = res.data
  } catch {
    analytics.value = null
  } finally {
    loadingAnalytics.value = false
  }
}

const loadTxns = async () => {
  const params = txnFilter.value !== 'all' ? `?txn_type=${txnFilter.value}` : ''
  const res = await api.get(`/api/properties/${propertyId}/transactions${params}`)
  transactions.value = res.data.transactions
  txnSummary.value = { income: res.data.income, expenses: res.data.expenses, net: res.data.net }
}

const loadDocs = async () => {
  const res = await api.get(`/api/documents?property_id=${propertyId}`)
  docs.value = res.data
}

const addTxn = async () => {
  savingTxn.value = true
  try {
    await api.post(`/api/properties/${propertyId}/transactions`, { ...txnForm.value, amount: Number(txnForm.value.amount) })
    showAddTxn.value = false
    txnForm.value = { type: 'income', amount: '', date: new Date().toISOString().slice(0,10), description: '', category: '' }
    await loadTxns()
    await loadAnalytics()
  } finally { savingTxn.value = false }
}

const deleteTxn = async (id) => {
  await api.delete(`/api/properties/${propertyId}/transactions/${id}`)
  await loadTxns()
  await loadAnalytics()
}

const uploadFile = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  uploadProgress.value = 10

  const { data } = await api.post('/api/documents/upload-url', {
    name: file.name, content_type: file.type,
    size_bytes: file.size, property_id: Number(propertyId)
  })
  uploadProgress.value = 30

  await fetch(data.upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': file.type } })
  uploadProgress.value = 80

  await api.post('/api/documents', {
    name: file.name, s3_key: data.s3_key, content_type: file.type,
    size_bytes: file.size, property_id: Number(propertyId)
  })
  uploadProgress.value = 100
  setTimeout(() => { uploadProgress.value = 0 }, 1000)
  await loadDocs()
  e.target.value = ''
}

const downloadDoc = async (doc) => {
  const { data } = await api.get(`/api/documents/${doc.id}/download-url`)
  window.open(data.download_url, '_blank')
}

const deleteDoc = async (id) => {
  await api.delete(`/api/documents/${id}`)
  docs.value = docs.value.filter(d => d.id !== id)
}

const loadLoanAccounts = async () => {
  loadingLoanAccounts.value = true
  try {
    const res = await api.get('/api/properties/mortgage-accounts')
    loanAccounts.value = res.data
  } finally {
    loadingLoanAccounts.value = false
  }
}

const linkMortgage = async () => {
  if (!selectedLoanAccount.value) return
  linking.value = true
  try {
    const res = await api.post(`/api/properties/${propertyId}/link-mortgage`, { account_id: selectedLoanAccount.value })
    property.value = res.data
    showLinkMortgage.value = false
    selectedLoanAccount.value = null
    await loadAnalytics()
  } finally { linking.value = false }
}

const unlinkMortgage = async () => {
  if (!confirm('Unlink this mortgage account? Mortgage fields will keep their current values.')) return
  const res = await api.delete(`/api/properties/${propertyId}/link-mortgage`)
  property.value = res.data
  await loadAnalytics()
}

const syncMortgage = async () => {
  syncing.value = true
  try {
    const res = await api.post(`/api/properties/${propertyId}/sync-mortgage`)
    property.value = res.data
    await loadAnalytics()
  } finally { syncing.value = false }
}

const applyEstimatedValue = async () => {
  const estimated = analytics.value?.current?.effective_current_value
  if (!estimated) return
  applyingEstimate.value = true
  try {
    const res = await api.put(`/api/properties/${propertyId}`, { current_value: Number(estimated) })
    property.value = res.data
    await loadAnalytics()
  } finally {
    applyingEstimate.value = false
  }
}

const saveCurrentValue = async () => {
  const raw = currentValueDraft.value
  if (raw === '' || raw == null) {
    currentValueStatus.value = 'Enter a value before saving'
    return
  }

  const parsed = Number(raw)
  if (!Number.isFinite(parsed) || parsed < 0) {
    currentValueStatus.value = 'Enter a valid non-negative number'
    return
  }

  savingCurrentValue.value = true
  currentValueStatus.value = ''
  try {
    const res = await api.put(`/api/properties/${propertyId}`, { current_value: parsed })
    property.value = res.data
    editingCurrentValue.value = false
    currentValueStatus.value = 'Current value saved'
    await loadAnalytics()
  } catch (err) {
    currentValueStatus.value = err.response?.data?.detail || 'Could not save current value'
  } finally {
    savingCurrentValue.value = false
  }
}

const enrichFromAddress = async () => {
  enrichingAddress.value = true
  enrichStatus.value = ''
  try {
    const res = await api.post(`/api/properties/${propertyId}/enrich-address`, {
      apply_current_value_if_empty: true,
      force_current_value: false,
      refresh_location_fields: false,
    })
    property.value = res.data.property
    await loadAnalytics()
    const updated = res.data.fields_updated || []
    enrichStatus.value = updated.length
      ? `Updated: ${updated.join(', ')}`
      : 'No additional online fields were applied'
  } catch (err) {
    enrichStatus.value = err.response?.data?.detail || 'Could not fetch online property details'
  } finally {
    enrichingAddress.value = false
  }
}

const fmtCurrency = (v) => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : null
const fmtRate = (v) => v != null ? `${Number(v).toFixed(3)}%` : null
const fmtDate = (v) => v ? v.slice(0, 10) : null

const handleImportFile = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  e.target.value = ''
  importingCsv.value = true

  const isJson = file.name.toLowerCase().endsWith('.json')
  const endpoint = isJson
    ? `/api/properties/${propertyId}/import-mortgage-json`
    : `/api/properties/${propertyId}/import-mortgage-csv`

  try {
    const form = new FormData()
    form.append('file', file)
    const res = await api.post(endpoint, form, { headers: { 'Content-Type': 'multipart/form-data' } })

    if (isJson) {
      const s = res.data.summary
      const rows = [
        { label: 'Principal Balance', value: fmtCurrency(s.balance) },
        { label: 'Interest Rate', value: fmtRate(s.rate) },
        { label: 'Monthly Payment', value: fmtCurrency(s.payment) },
        s.pi_payment != null ? { label: 'P&I Payment', value: fmtCurrency(s.pi_payment) } : null,
        s.escrow_payment != null ? { label: 'Escrow Payment', value: fmtCurrency(s.escrow_payment) } : null,
        s.loan_id ? { label: 'Loan ID', value: s.loan_id } : null,
        s.original_balance != null ? { label: 'Original Balance', value: fmtCurrency(s.original_balance) } : null,
        s.maturity_date ? { label: 'Maturity Date', value: fmtDate(s.maturity_date) } : null,
        s.last_payment_date ? { label: 'Last Payment', value: fmtDate(s.last_payment_date) } : null,
        s.payment_due_date ? { label: 'Next Payment Due', value: fmtDate(s.payment_due_date) } : null,
      ].filter(Boolean)
      csvResult.value = { source: 'json', displayRows: rows }
    } else {
      csvResult.value = { source: 'csv', ...res.data }
      await loadTxns()
    }

    property.value = res.data.property
    await loadAnalytics()
    showCsvResult.value = true
  } catch (err) {
    const msg = err.response?.data?.detail || `${isJson ? 'JSON' : 'CSV'} import failed`
    alert(msg)
  } finally {
    importingCsv.value = false
  }
}

watch(showLinkMortgage, (open) => {
  if (open && loanAccounts.value.length === 0) loadLoanAccounts()
})

watch(() => property.value?.mortgage_rate, (rate) => {
  if ((projectionInterestRate.value === '' || projectionInterestRate.value == null) && rate != null) {
    projectionInterestRate.value = Number(rate)
  }
}, { immediate: true })

watch(historyMonths, async () => {
  await loadAnalytics()
})

onMounted(async () => {
  await Promise.all([loadProperty(), loadTxns(), loadDocs(), loadLoanAccounts(), loadAnalytics(), loadPropertyPlans()])
})
</script>
