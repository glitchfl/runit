Output capture.gif

Set Shell "bash"
Set FontSize 22
Set Width 1400
Set Height 600
Set Padding 30
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set FontFamily "Menlo"
Set Framerate 30

Sleep 500ms

Type "runit add greet '@user whoami' 'echo Hello, {user}!'"
Enter
Sleep 1200ms

Type "runit greet"
Enter
Sleep 2500ms
