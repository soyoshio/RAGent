# React Hooks 技术指南

## useState

`useState` 让你在函数组件中使用状态。

```javascript
const [count, setCount] = useState(0);
```

## useEffect

`useEffect` 用于处理副作用，例如数据获取、订阅或手动修改 DOM。

```javascript
useEffect(() => {
  document.title = `Count: ${count}`;
}, [count]);
```

## useContext

`useContext` 让你订阅 React Context。

## 规则

- 只在最顶层调用 Hook
- 只在 React 函数中调用 Hook
