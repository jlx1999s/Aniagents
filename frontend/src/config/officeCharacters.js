function createPixelAvatar({ body, hair, accent, accessory }) {
  const accessoryMap = {
    beret: '<rect x="8" y="6" width="16" height="4" fill="#282c34"/><rect x="20" y="5" width="4" height="2" fill="#282c34"/>',
    glasses: '<rect x="9" y="16" width="5" height="3" fill="#2e3440"/><rect x="18" y="16" width="5" height="3" fill="#2e3440"/><rect x="14" y="17" width="4" height="1" fill="#2e3440"/>',
    hair: '<rect x="22" y="12" width="3" height="3" fill="#f0b3d7"/>',
    pencil: '<rect x="23" y="12" width="1" height="8" fill="#f5d38a"/><rect x="23" y="20" width="1" height="1" fill="#2e3440"/>',
    headphones: '<rect x="8" y="13" width="2" height="6" fill="#434c5e"/><rect x="22" y="13" width="2" height="6" fill="#434c5e"/><rect x="10" y="11" width="12" height="2" fill="#434c5e"/>'
  };
  const accessorySvg = accessoryMap[accessory] || '';
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" shape-rendering="crispEdges">
      <rect width="32" height="32" rx="4" fill="#0b1020"/>
      <rect x="1" y="1" width="30" height="30" rx="3" fill="${accent}" opacity="0.22"/>
      <rect x="8" y="10" width="16" height="3" fill="${hair}"/>
      <rect x="9" y="13" width="14" height="10" fill="#f2d3b2"/>
      <rect x="11" y="17" width="2" height="2" fill="#2f3545"/>
      <rect x="19" y="17" width="2" height="2" fill="#2f3545"/>
      <rect x="10" y="24" width="12" height="6" fill="${body}"/>
      <rect x="9" y="30" width="14" height="1" fill="#2f3545"/>
      ${accessorySvg}
    </svg>
  `;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export const officeCharacterLibrary = {
  director: {
    role: '导演',
    sprite: createPixelAvatar({ body: '#e06c75', hair: '#282c34', accent: '#e06c75', accessory: 'beret' })
  },
  Scriptwriter_Agent: {
    actor: '分镜师',
    sprite: createPixelAvatar({ body: '#61afef', hair: '#d19a66', accent: '#61afef', accessory: 'glasses' }),
    accent: 'amber'
  },
  Art_Director_Agent: {
    actor: '美术总监',
    sprite: createPixelAvatar({ body: '#e06c75', hair: '#282c34', accent: '#e06c75', accessory: 'beret' }),
    accent: 'director'
  },
  Character_Designer_Agent: {
    actor: '角色设计师',
    sprite: createPixelAvatar({ body: '#c678dd', hair: '#98c379', accent: '#c678dd', accessory: 'hair' }),
    accent: 'magenta'
  },
  Scene_Designer_Agent: {
    actor: '场景设计师',
    sprite: createPixelAvatar({ body: '#7fdbca', hair: '#4b5563', accent: '#7fdbca', accessory: 'pencil' }),
    accent: 'cyan'
  },
  Storyboard_Artist_Agent: {
    actor: '分镜画师',
    sprite: createPixelAvatar({ body: '#98c379', hair: '#e5c07b', accent: '#98c379', accessory: 'pencil' }),
    accent: 'cyan'
  },
  Animation_Artist_Agent: {
    actor: '动画师',
    sprite: createPixelAvatar({ body: '#e5c07b', hair: '#5c6370', accent: '#e5c07b', accessory: 'headphones' }),
    accent: 'violet'
  },
  Sound_Director_Agent: {
    actor: '音频总监',
    sprite: createPixelAvatar({ body: '#56b6c2', hair: '#abb2bf', accent: '#56b6c2', accessory: 'headphones' }),
    accent: 'cyan'
  },
  Compositor_Agent: {
    actor: '合成师',
    sprite: createPixelAvatar({ body: '#d19a66', hair: '#4b5563', accent: '#d19a66', accessory: 'glasses' }),
    accent: 'amber'
  }
};
