// Quel micro un processus utilise-t-il vraiment ? (macOS 14+, objets « process » de CoreAudio)
//
//   mic-status <PID>   noms des entrées audio en cours d'utilisation par ce processus, une par ligne
//   mic-status         noms de toutes les entrées audio présentes, une par ligne
//
// Sert à vérifier que BirdNET-Go capte bien le micro de config.yaml : si ce micro disparaît
// (débranché, coupure USB), macOS bascule la capture sur l'entrée par défaut sans que
// BirdNET-Go le voie, et ne revient pas en arrière quand le micro réapparaît.
import CoreAudio
import Foundation

func address(_ selector: AudioObjectPropertySelector,
             _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal) -> AudioObjectPropertyAddress {
  AudioObjectPropertyAddress(mSelector: selector, mScope: scope, mElement: kAudioObjectPropertyElementMain)
}

func objectIDs(_ object: AudioObjectID, _ addr: AudioObjectPropertyAddress) -> [AudioObjectID] {
  var a = addr
  var size: UInt32 = 0
  guard AudioObjectGetPropertyDataSize(object, &a, 0, nil, &size) == noErr, size > 0 else { return [] }
  var ids = [AudioObjectID](repeating: 0, count: Int(size) / MemoryLayout<AudioObjectID>.size)
  guard AudioObjectGetPropertyData(object, &a, 0, nil, &size, &ids) == noErr else { return [] }
  return ids
}

func name(_ device: AudioObjectID) -> String {
  var a = address(kAudioObjectPropertyName)
  var value: Unmanaged<CFString>?
  var size = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
  guard AudioObjectGetPropertyData(device, &a, 0, nil, &size, &value) == noErr,
        let s = value?.takeRetainedValue() else { return "?" }
  return s as String
}

func hasInput(_ device: AudioObjectID) -> Bool {
  !objectIDs(device, address(kAudioDevicePropertyStreams, kAudioDevicePropertyScopeInput)).isEmpty
}

let system = AudioObjectID(kAudioObjectSystemObject)
let args = CommandLine.arguments

if args.count < 2 {
  for device in objectIDs(system, address(kAudioHardwarePropertyDevices)) where hasInput(device) {
    print(name(device))
  }
} else if let pid = pid_t(args[1]) {
  for process in objectIDs(system, address(kAudioHardwarePropertyProcessObjectList)) {
    var a = address(kAudioProcessPropertyPID)
    var processPID: pid_t = 0
    var size = UInt32(MemoryLayout<pid_t>.size)
    guard AudioObjectGetPropertyData(process, &a, 0, nil, &size, &processPID) == noErr,
          processPID == pid else { continue }
    for device in objectIDs(process, address(kAudioProcessPropertyDevices, kAudioObjectPropertyScopeInput)) {
      print(name(device))
    }
  }
} else {
  FileHandle.standardError.write("usage : mic-status [PID]\n".data(using: .utf8)!)
  exit(2)
}
