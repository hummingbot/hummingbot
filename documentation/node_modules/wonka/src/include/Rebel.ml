#if BS_NATIVE then
  #if BSB_BACKEND = "js" then
    include Rebel_js
  #else
    include Rebel_native
  #end
#else
  include Rebel_js
#end
