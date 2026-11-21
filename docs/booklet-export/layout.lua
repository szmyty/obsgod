-- Optional documentation export only; never loaded by the plugin or its build.
function Header(element)
  if element.level == 1 then return {} end -- The PDF metadata supplies the title.
  element.level = element.level - 1
  local title = pandoc.utils.stringify(element.content)
  if title:match('^Page [2-9] ') or title:match('^Page 10 ')
      or title == 'If any step fails' or title == 'Coverage and later work' then
    return {pandoc.RawBlock('latex', '\\clearpage'), element}
  end
  return element
end

function Link(element)
  local target = element.target
  if target:match('^#') or target:match('^[%a][%w+.-]*:') then return element end
  local base = 'https://github.com/szmyty/obsgod/blob/a2137bf214c77efda3ce3fb87879f88004c6477c/'
  if target:match('^%.%./') then
    element.target = base .. target:sub(4)
  else
    element.target = base .. 'docs/' .. target
  end
  return element
end

function Table(element)
  if #element.colspecs == 2 then
    element.colspecs = {
      {element.colspecs[1][1], 0.5},
      {element.colspecs[2][1], 0.5}
    }
  end
  return element
end
